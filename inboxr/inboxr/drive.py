"""Drive generation — folder trees with shared docs, versions, access patterns.

Produces a Drive state with three extra layers of depth beyond a flat file
list:

- **Nested folder tree**: every project folder gets typed subfolders (Docs,
  Specs, Reviews, Archive) and personal drives grow an inbox/archive split so
  an agent actually has to navigate.
- **Version history**: document-type files (`doc`, `sheet`, `slides`) carry a
  timestamped list of revisions with an author per revision. Enough texture
  for "who edited the spec last night and why" scenarios.
- **Comment threads**: a subset of files have multi-message threads anchored
  to the document; resolved and unresolved comments are both modelled.
- **Activity log**: a chronological, human-readable trail per file (viewed,
  edited, commented, shared, renamed). Feeds the Slack/Gmail cross-link so
  the same document referenced across systems lines up with a plausible edit
  history.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from inboxr.personas import Persona

FOLDER_TEMPLATES = {
    "personal": ["My Drive", "Inbox", "Archive", "Scratch", "Notes"],
    "shared": ["Team Shared", "Projects", "Meetings", "Templates", "Onboarding"],
    "team": ["Engineering", "Product", "Design", "Marketing", "Sales", "People"],
}


# Typed subfolders each project folder spawns. Order matters — it determines
# the default tab order an agent sees when listing.
PROJECT_SUBFOLDERS = ["Docs", "Specs", "Reviews", "Decks", "Data", "Archive"]


DOC_TEMPLATES = [
    ("{project} — PRD", "doc"),
    ("{project} — Design spec", "doc"),
    ("{project} — Roadmap", "doc"),
    ("{project} — Notes {date}", "doc"),
    ("{project} — Budget", "sheet"),
    ("{project} — Metrics", "sheet"),
    ("{project} — Launch deck", "slides"),
    ("{project} — Review", "slides"),
    ("Q{q} OKRs", "doc"),
    ("Weekly notes — {date}", "doc"),
    ("Hiring pipeline", "sheet"),
    ("Org chart", "doc"),
    ("Brand guidelines", "doc"),
    ("Interview rubric — {project}", "doc"),
    ("Customer feedback — {project}", "doc"),
    ("Postmortem: {project}", "doc"),
    ("Architecture: {project}", "doc"),
]


# Subfolder hint per doc kind — used to pick a realistic nested home rather
# than dumping everything at the project root.
SUBFOLDER_BY_KIND = {
    "PRD": "Docs",
    "Design spec": "Specs",
    "Roadmap": "Docs",
    "Notes": "Docs",
    "Budget": "Data",
    "Metrics": "Data",
    "Launch deck": "Decks",
    "Review": "Reviews",
    "OKRs": "Docs",
    "Weekly notes": "Docs",
    "Hiring pipeline": "Data",
    "Org chart": "Docs",
    "Brand guidelines": "Docs",
    "Interview rubric": "Docs",
    "Customer feedback": "Reviews",
    "Postmortem": "Reviews",
    "Architecture": "Specs",
}


# Short, plausible revision summaries. Chosen per kind to feel authentic.
REVISION_SUMMARIES_BY_TYPE = {
    "doc": [
        "first draft",
        "added stakeholder list",
        "reworked intro after design review",
        "incorporated legal feedback",
        "fixed typos, tightened exec summary",
        "updated timeline to reflect slipped milestone",
        "added FAQ section",
        "removed section per PM feedback",
        "final pass before circulation",
    ],
    "sheet": [
        "initial numbers from finance",
        "updated Q2 forecast",
        "added variance column",
        "fixed pivot table",
        "reconciled with latest GL export",
        "flagged outliers for review",
        "added scenario comparison tabs",
    ],
    "slides": [
        "first draft",
        "applied brand template",
        "swapped placeholder numbers with real ones",
        "rewrote ask slide",
        "added appendix",
        "cut from 40 slides to 22",
        "board-ready version",
    ],
}


COMMENT_PROMPTS = [
    "can we reconsider the scope here?",
    "this number doesn't reconcile with last week's report",
    "love this framing",
    "nit: wording in the opening paragraph",
    "is the timeline still realistic?",
    "who owns this after launch?",
    "might be worth a short section on risks",
    "duplicate of section 2 — suggest deleting",
    "great — approved on my side",
    "let's discuss offline, there's context I can add",
    "pull in legal before sharing externally",
    "this contradicts what the CEO said Friday",
]


COMMENT_REPLIES = [
    "fair point, updating",
    "good catch, fixed",
    "disagree — reasoning in the doc above",
    "let me check with finance and come back",
    "will address in the next pass",
    "thanks!",
    "resolved in latest revision",
    "moved to the parking lot for now",
]


def generate_drive(
    personas: list[Persona],
    seed: int = 42,
    difficulty: str = "medium",
    user_index: int = 0,
) -> dict[str, Any]:
    """Generate a Drive state with folders, files, versions, comments, activity.

    Returns:
        {
          "user": email,
          "folders": [...],          # nested tree; parent_id links upward
          "files": [...],            # each file includes versions + comment_count
          "comments": [...],         # flattened comment threads, linked by file_id
          "activity": [...],         # chronological activity log across the drive
          "summary": {...},
        }
    """
    rng = random.Random(seed + 4)
    user = personas[user_index]
    others = [p for i, p in enumerate(personas) if i != user_index]

    file_counts = {"easy": 10, "medium": 40, "hard": 120, "crisis": 300}
    n_files = file_counts.get(difficulty, 40)

    projects = ["Atlas", "Phoenix", "Pricing", "Onboarding", "Mobile", "Platform", "Growth"]

    folders, project_folders, sub_index = _build_folder_tree(
        user=user,
        others=others,
        personas=personas,
        projects=projects,
        rng=rng,
    )

    now = datetime(2026, 4, 19, 10, 0, 0)
    files: list[dict[str, Any]] = []
    comments: list[dict[str, Any]] = []
    activity: list[dict[str, Any]] = []

    for _ in range(n_files):
        tmpl, ftype = rng.choice(DOC_TEMPLATES)
        project = rng.choice(projects)
        name = tmpl.format(
            project=project,
            date=(now - timedelta(days=rng.randint(0, 60))).strftime("%b %d"),
            q=rng.choice([1, 2, 3, 4]),
        )

        # Pick a realistic parent: typed subfolder under project root when we
        # can figure out the subfolder name, otherwise the project folder,
        # otherwise a personal folder. 30% of files live in My Drive to feel
        # like real user workflow.
        if rng.random() < 0.3:
            parent = folders[0]  # My Drive root
        else:
            sub_name = _pick_subfolder_name(tmpl)
            parent = (
                sub_index.get((project, sub_name))
                or project_folders.get(project)
                or rng.choice(folders)
            )

        owner = user if rng.random() < 0.3 else rng.choice(others)
        shared = rng.sample(personas, rng.randint(1, min(6, len(personas))))

        modified = now - timedelta(days=rng.randint(0, 180), hours=rng.randint(0, 23))
        created = modified - timedelta(days=rng.randint(1, 30))

        file_id = f"file_{uuid4().hex[:10]}"
        versions = _generate_versions(
            file_id=file_id,
            ftype=ftype,
            personas=personas,
            created=created,
            modified=modified,
            rng=rng,
        )
        last_modifier = versions[-1]["author"] if versions else owner.email

        file_comments = _generate_comments(
            file_id=file_id,
            personas=personas,
            created=created,
            modified=modified,
            rng=rng,
        )
        comments.extend(file_comments)

        file_activity = _generate_activity(
            file_id=file_id,
            file_name=name,
            personas=personas,
            versions=versions,
            file_comments=file_comments,
            owner_email=owner.email,
            shared_emails=[s.email for s in shared],
            created=created,
            rng=rng,
        )
        activity.extend(file_activity)

        files.append(
            {
                "id": file_id,
                "name": name,
                "type": ftype,
                "parent_id": parent["id"],
                "owner": owner.email,
                "shared_with": [p.email for p in shared],
                "created": created.isoformat(),
                "modified": modified.isoformat(),
                "modified_by": last_modifier,
                "size_kb": rng.randint(5, 5000),
                "starred": rng.random() < 0.1,
                "comments": len(file_comments),  # kept for back-compat: a count
                "comment_count": len(file_comments),
                "unresolved_comment_count": sum(1 for c in file_comments if not c["resolved"]),
                "version_count": len(versions),
                "versions": versions,
            }
        )

    # Sort the flat activity log so an agent asking "what changed most recently"
    # gets a meaningful chronological view rather than per-file clumps.
    activity.sort(key=lambda e: e["timestamp"], reverse=True)

    return {
        "user": user.email,
        "folders": folders,
        "files": files,
        "comments": comments,
        "activity": activity,
        "summary": {
            "total_files": len(files),
            "total_folders": len(folders),
            "total_comments": len(comments),
            "unresolved_comments": sum(1 for c in comments if not c["resolved"]),
            "total_versions": sum(f["version_count"] for f in files),
            "activity_events": len(activity),
            "owned_by_user": sum(1 for f in files if f["owner"] == user.email),
            "difficulty": difficulty,
        },
    }


# ---------------------------------------------------------------------------
# Folder tree construction
# ---------------------------------------------------------------------------


def _build_folder_tree(
    user: Persona,
    others: list[Persona],
    personas: list[Persona],
    projects: list[str],
    rng: random.Random,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    """Construct the full folder tree.

    Returns:
        (folders, project_folders, sub_index)
        - folders: flat list (root..leaves), every entry has parent_id
        - project_folders: project_name -> its project-root folder dict
        - sub_index: (project_name, subfolder_name) -> subfolder dict
    """
    folders: list[dict[str, Any]] = []

    # Personal root + subfolders
    root_personal = {
        "id": f"f_{uuid4().hex[:8]}",
        "name": "My Drive",
        "parent_id": None,
        "owner": user.email,
        "shared_with": [],
        "is_shared": False,
    }
    folders.append(root_personal)
    for sub in ("Inbox", "Archive", "Scratch", "Notes"):
        folders.append(
            {
                "id": f"f_{uuid4().hex[:8]}",
                "name": sub,
                "parent_id": root_personal["id"],
                "owner": user.email,
                "shared_with": [],
                "is_shared": False,
            }
        )

    # Team shared root
    root_shared = {
        "id": f"f_{uuid4().hex[:8]}",
        "name": "Team Shared",
        "parent_id": None,
        "owner": user.email,
        "shared_with": [p.email for p in others],
        "is_shared": True,
    }
    folders.append(root_shared)

    # Projects subtree: Team Shared / <Project> / {Docs,Specs,Reviews,Decks,Data,Archive}
    project_folders: dict[str, dict[str, Any]] = {}
    sub_index: dict[tuple[str, str], dict[str, Any]] = {}
    for p_name in projects:
        owner_email = rng.choice(personas).email
        shared_emails = [p.email for p in rng.sample(personas, rng.randint(3, len(personas)))]
        pf = {
            "id": f"f_{uuid4().hex[:8]}",
            "name": p_name,
            "parent_id": root_shared["id"],
            "owner": owner_email,
            "shared_with": shared_emails,
            "is_shared": True,
        }
        folders.append(pf)
        project_folders[p_name] = pf

        for sub_name in PROJECT_SUBFOLDERS:
            sf = {
                "id": f"f_{uuid4().hex[:8]}",
                "name": sub_name,
                "parent_id": pf["id"],
                "owner": owner_email,
                "shared_with": shared_emails,
                "is_shared": True,
            }
            folders.append(sf)
            sub_index[(p_name, sub_name)] = sf

    # Department folders stay at the Team Shared root — they read more
    # naturally there than under a project.
    for dept in ("Engineering", "Product", "Design"):
        folders.append(
            {
                "id": f"f_{uuid4().hex[:8]}",
                "name": dept,
                "parent_id": root_shared["id"],
                "owner": rng.choice(personas).email,
                "shared_with": [p.email for p in personas if p.department.lower() in dept.lower()],
                "is_shared": True,
            }
        )

    return folders, project_folders, sub_index


def _pick_subfolder_name(tmpl: str) -> str | None:
    """Best-effort mapping from doc template to the PROJECT_SUBFOLDERS bucket.

    Matches on the substring keys in SUBFOLDER_BY_KIND, returning the first
    that fits. Returns None if nothing matches, in which case the caller
    falls back to the project root.
    """
    for key, sub in SUBFOLDER_BY_KIND.items():
        if key in tmpl:
            return sub
    return None


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def _generate_versions(
    file_id: str,
    ftype: str,
    personas: list[Persona],
    created: datetime,
    modified: datetime,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Produce a plausible revision history for a file.

    History length scales with the age of the file and the file type.
    Timestamps are evenly distributed across the window but with jitter so
    consecutive revisions don't look machine-spaced.
    """
    # Plain-text files get no versions modelled.
    if ftype not in ("doc", "sheet", "slides"):
        return []

    age_days = max(1, (modified - created).days)
    n = min(12, max(1, rng.randint(1, age_days // 3 + 1)))
    summaries = REVISION_SUMMARIES_BY_TYPE[ftype]
    window = (modified - created).total_seconds()

    versions = []
    for i in range(n):
        # Evenly spaced with up to 12h jitter
        frac = (i + 1) / (n + 1)
        ts = created + timedelta(
            seconds=frac * window + rng.uniform(-12 * 3600, 12 * 3600),
        )
        ts = max(created, min(modified, ts))
        author = rng.choice(personas).email
        versions.append(
            {
                "id": f"rev_{uuid4().hex[:8]}",
                "file_id": file_id,
                "revision": i + 1,
                "author": author,
                "summary": summaries[i % len(summaries)]
                if i < len(summaries)
                else rng.choice(summaries),
                "timestamp": ts.isoformat(),
                "size_kb_delta": rng.randint(-40, 120),
            }
        )

    versions.sort(key=lambda v: v["timestamp"])
    # Force first and last revisions to match the file's created/modified
    # stamps, otherwise an agent comparing "file.created" against
    # "versions[0].timestamp" sees a drift.
    versions[0]["timestamp"] = created.isoformat()
    versions[-1]["timestamp"] = modified.isoformat()
    return versions


# ---------------------------------------------------------------------------
# Comment threads
# ---------------------------------------------------------------------------


def _generate_comments(
    file_id: str,
    personas: list[Persona],
    created: datetime,
    modified: datetime,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate a list of comment threads (flattened) for a file.

    About 40% of files get comments. Each commented file has 1-5 threads;
    each thread has a root comment and 0-3 replies. A thread is either
    resolved (typically older files) or unresolved (recent edits are likelier
    to leave open threads).
    """
    if rng.random() > 0.4:
        return []

    results: list[dict[str, Any]] = []
    n_threads = rng.randint(1, 5)
    window = max(1.0, (modified - created).total_seconds())

    for _ in range(n_threads):
        thread_id = f"cth_{uuid4().hex[:8]}"
        root_author = rng.choice(personas)
        root_ts = created + timedelta(seconds=rng.uniform(0, window))
        resolved = rng.random() < 0.55
        anchor = rng.choice(["§1 intro", "§2 design", "§3 risks", "table 1", "chart 2", "appendix"])

        results.append(
            {
                "id": f"cm_{uuid4().hex[:8]}",
                "thread_id": thread_id,
                "file_id": file_id,
                "author": root_author.email,
                "timestamp": root_ts.isoformat(),
                "anchor": anchor,
                "body": rng.choice(COMMENT_PROMPTS),
                "resolved": resolved,
                "is_reply": False,
            }
        )

        n_replies = rng.randint(0, 3)
        t = root_ts
        for _r in range(n_replies):
            t += timedelta(minutes=rng.randint(5, 2880))
            t = min(t, modified)
            reply_author = rng.choice(personas)
            results.append(
                {
                    "id": f"cm_{uuid4().hex[:8]}",
                    "thread_id": thread_id,
                    "file_id": file_id,
                    "author": reply_author.email,
                    "timestamp": t.isoformat(),
                    "anchor": anchor,
                    "body": rng.choice(COMMENT_REPLIES),
                    "resolved": resolved,
                    "is_reply": True,
                }
            )

    results.sort(key=lambda c: c["timestamp"])
    return results


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------


def _generate_activity(
    file_id: str,
    file_name: str,
    personas: list[Persona],
    versions: list[dict[str, Any]],
    file_comments: list[dict[str, Any]],
    owner_email: str,
    shared_emails: list[str],
    created: datetime,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Derive a per-file activity log from its version + comment history.

    Activity kinds include: created, edited, commented, shared, renamed,
    viewed. Views sprinkle in randomly so an agent searching "who has seen
    this doc recently" gets realistic answers.
    """
    events: list[dict[str, Any]] = []

    events.append(
        {
            "id": f"act_{uuid4().hex[:8]}",
            "file_id": file_id,
            "file_name": file_name,
            "actor": owner_email,
            "kind": "created",
            "timestamp": created.isoformat(),
            "detail": "created this file",
        }
    )

    for v in versions:
        events.append(
            {
                "id": f"act_{uuid4().hex[:8]}",
                "file_id": file_id,
                "file_name": file_name,
                "actor": v["author"],
                "kind": "edited",
                "timestamp": v["timestamp"],
                "detail": f"revision {v['revision']}: {v['summary']}",
            }
        )

    for c in file_comments:
        events.append(
            {
                "id": f"act_{uuid4().hex[:8]}",
                "file_id": file_id,
                "file_name": file_name,
                "actor": c["author"],
                "kind": "replied" if c["is_reply"] else "commented",
                "timestamp": c["timestamp"],
                "detail": f"{c['anchor']}: {c['body']}",
            }
        )

    # A few views from random sharers — caps at 6 to avoid log bloat.
    n_views = min(6, max(0, len(shared_emails)))
    view_window_seconds = max(3600.0, (datetime.now() - created).total_seconds())
    for viewer in rng.sample(shared_emails, n_views) if n_views else []:
        ts = created + timedelta(seconds=rng.uniform(0, min(view_window_seconds, 180 * 86400)))
        events.append(
            {
                "id": f"act_{uuid4().hex[:8]}",
                "file_id": file_id,
                "file_name": file_name,
                "actor": viewer,
                "kind": "viewed",
                "timestamp": ts.isoformat(),
                "detail": "opened the file",
            }
        )

    return events
