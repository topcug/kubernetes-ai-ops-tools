"""Consistency engine — validates cross-system coherence of a generated workspace.

A generated workspace is "consistent" when the same people, projects, meetings, and
documents referenced in one system are discoverable in the others. This module
detects violations and (optionally) repairs them by linking orphan references
into the appropriate system.

The engine now operates in two layers:

1. **Reference integrity** — every email address, user id, folder id, file id,
   attendee, comment author, activity actor, and reply-target must resolve to
   a known entity. Violations here are `error` severity and mechanically
   repairable.

2. **Graph-based coherence** — a derived :class:`ReferenceGraph` links
   personas, projects, and artifacts across systems. It powers richer checks
   like "this project is discussed but never grounded in a file or meeting",
   "this persona appears in emails but nowhere else", and "this file has an
   activity trail that pre-dates its creation timestamp". Graph-level
   violations default to `warning` but the repair pass can now close the
   most common ones automatically (currently: `project_without_artifact` by
   synthesising a stub Drive document in the right project folder).

Two entry points:
    check(workspace)   -> ConsistencyReport
    repair(workspace)  -> (repaired_workspace, ConsistencyReport)
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Violation:
    """A single cross-system consistency violation."""

    code: str  # short stable identifier, e.g. "orphan_email_sender"
    severity: str  # "error" | "warning" | "info"
    system: str  # "gmail" | "slack" | "calendar" | "drive" | "whatsapp" | "cross"
    message: str  # human-readable description
    ref: dict[str, Any] = field(default_factory=dict)  # ids/pointers for tooling


@dataclass
class ConsistencyReport:
    """Aggregate report for a workspace check."""

    violations: list[Violation] = field(default_factory=list)
    repaired: list[Violation] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    @property
    def is_consistent(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_consistent": self.is_consistent,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "violations": [asdict(v) for v in self.violations],
            "repaired": [asdict(v) for v in self.repaired],
        }

    def summary(self) -> str:
        lines = [
            f"Consistency: {'OK' if self.is_consistent else 'FAILED'}",
            f"  errors:   {self.error_count}",
            f"  warnings: {self.warning_count}",
            f"  repaired: {len(self.repaired)}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Index — a derived view of the workspace used by every check
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceIndex:
    """Pre-computed lookups so checks stay O(n) instead of O(n²)."""

    emails_by_persona: dict[str, str]  # persona_id -> email
    ids_by_email: dict[str, str]  # email -> persona_id
    slack_handles: set[str]  # set of @handles present
    persona_ids: set[str]
    persona_emails: set[str]
    project_tokens: set[str]  # lowercase project names mentioned anywhere
    folder_ids: set[str]
    file_ids: set[str]
    message_ids_by_chat: dict[str, set[str]]  # whatsapp chat_id -> set of message ids
    user_email: str
    user_id: str

    @classmethod
    def build(cls, workspace: dict[str, Any]) -> WorkspaceIndex:
        personas = workspace.get("personas", [])
        emails_by_persona = {p["id"]: p["email"] for p in personas}
        ids_by_email = {p["email"]: p["id"] for p in personas}
        slack_handles = {p.get("slack_handle", "") for p in personas if p.get("slack_handle")}

        # Collect project tokens from every system so we can detect which
        # are referenced in one system and absent from another.
        project_tokens: set[str] = set()
        for thread in workspace.get("gmail", {}).get("threads", []):
            project_tokens.update(_extract_projects(thread.get("subject", "")))
            for msg in thread.get("messages", []):
                project_tokens.update(_extract_projects(msg.get("body", "")))

        for ch in workspace.get("slack", {}).get("channels", []):
            for m in ch.get("messages", []):
                project_tokens.update(_extract_projects(m.get("text", "")))

        for ev in workspace.get("calendar", {}).get("events", []):
            project_tokens.update(_extract_projects(ev.get("title", "")))

        for f in workspace.get("drive", {}).get("files", []):
            project_tokens.update(_extract_projects(f.get("name", "")))

        folder_ids = {f["id"] for f in workspace.get("drive", {}).get("folders", [])}
        file_ids = {f["id"] for f in workspace.get("drive", {}).get("files", [])}

        message_ids_by_chat: dict[str, set[str]] = {}
        for chat in workspace.get("whatsapp", {}).get("chats", []):
            message_ids_by_chat[chat.get("id", "")] = {
                m.get("id", "") for m in chat.get("messages", [])
            }

        meta = workspace.get("meta", {})
        return cls(
            emails_by_persona=emails_by_persona,
            ids_by_email=ids_by_email,
            slack_handles=slack_handles,
            persona_ids=set(emails_by_persona.keys()),
            persona_emails=set(ids_by_email.keys()),
            project_tokens=project_tokens,
            folder_ids=folder_ids,
            file_ids=file_ids,
            message_ids_by_chat=message_ids_by_chat,
            user_email=meta.get("user_email", ""),
            user_id=ids_by_email.get(meta.get("user_email", ""), ""),
        )


# ---------------------------------------------------------------------------
# Reference graph — nodes are entities, edges are cross-system mentions.
# ---------------------------------------------------------------------------


# Node types we track in the graph. Kept small on purpose — the point is to
# reason about cross-system coverage, not to be a general-purpose ontology.
NODE_PERSONA = "persona"
NODE_PROJECT = "project"
NODE_FILE = "file"
NODE_EVENT = "event"


@dataclass
class ReferenceGraph:
    """A cross-system mention graph over personas, projects, and artifacts.

    Edges are typed by the source system so the engine can answer questions
    like "which projects only live in conversation" (gmail/slack edges but no
    drive/calendar edges) or "which personas are never mentioned in email".

    Nodes are keyed by `(node_type, identity)`:
      - persona: identity = persona_id
      - project: identity = lowercase project token
      - file:    identity = file_id
      - event:   identity = event_id
    """

    # node_key -> set of systems that reference it
    node_systems: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    # directed edges grouped by source system: edges_by_system[system] = set((src, dst))
    edges_by_system: dict[str, set[tuple[tuple[str, str], tuple[str, str]]]] = field(
        default_factory=dict
    )

    def _touch(self, node: tuple[str, str], system: str) -> None:
        self.node_systems.setdefault(node, set()).add(system)

    def add_edge(
        self,
        src: tuple[str, str],
        dst: tuple[str, str],
        system: str,
    ) -> None:
        self._touch(src, system)
        self._touch(dst, system)
        self.edges_by_system.setdefault(system, set()).add((src, dst))

    def systems_for(self, node: tuple[str, str]) -> set[str]:
        return set(self.node_systems.get(node, set()))

    def nodes_of_type(self, node_type: str) -> list[tuple[str, str]]:
        return [n for n in self.node_systems if n[0] == node_type]

    @classmethod
    def build(cls, workspace: dict[str, Any], idx: WorkspaceIndex) -> ReferenceGraph:
        g = cls()

        # Every persona is a node in its own right so we can ask the graph
        # whether a persona ever surfaces in any system at all.
        for pid in idx.persona_ids:
            g._touch((NODE_PERSONA, pid), "personas")

        # Gmail edges: sender persona -> recipient personas, plus any
        # project tokens found in subject/body become project nodes linked
        # to both the sender and recipients.
        for thread in workspace.get("gmail", {}).get("threads", []):
            project_tokens = set(_extract_projects(thread.get("subject", "")))
            for msg in thread.get("messages", []):
                project_tokens.update(_extract_projects(msg.get("body", "")))
                sender = idx.ids_by_email.get(msg.get("from", ""))
                for recipient_email in msg.get("to", []) + msg.get("cc", []):
                    recipient = idx.ids_by_email.get(recipient_email)
                    if sender and recipient:
                        g.add_edge(
                            (NODE_PERSONA, sender),
                            (NODE_PERSONA, recipient),
                            "gmail",
                        )
                for token in project_tokens:
                    proj = (NODE_PROJECT, token)
                    if sender:
                        g.add_edge((NODE_PERSONA, sender), proj, "gmail")

        # Slack edges: channel message author -> project tokens in the text.
        # We don't model channel membership here — the reference-integrity
        # check already handles that. The goal is *project coverage*.
        for ch in workspace.get("slack", {}).get("channels", []):
            for m in ch.get("messages", []):
                sender = m.get("user")
                if not sender:
                    continue
                for token in _extract_projects(m.get("text", "")):
                    g.add_edge((NODE_PERSONA, sender), (NODE_PROJECT, token), "slack")

        # Calendar edges: organizer persona -> project in title; attendees
        # become co-incident with that project.
        for ev in workspace.get("calendar", {}).get("events", []):
            ev_node = (NODE_EVENT, ev.get("id", ""))
            organizer = idx.ids_by_email.get(ev.get("organizer", ""))
            title_projects = _extract_projects(ev.get("title", ""))
            if organizer:
                g._touch((NODE_PERSONA, organizer), "calendar")
            for attendee_email in ev.get("attendees", []):
                attendee = idx.ids_by_email.get(attendee_email)
                if attendee:
                    g.add_edge((NODE_PERSONA, attendee), ev_node, "calendar")
                    for token in title_projects:
                        g.add_edge((NODE_PERSONA, attendee), (NODE_PROJECT, token), "calendar")

        # Drive edges: owner persona -> file node, file -> project token
        # found in the file's name. The dual edge means both persona and
        # project end up covered by the `drive` system tag.
        for f in workspace.get("drive", {}).get("files", []):
            file_node = (NODE_FILE, f.get("id", ""))
            owner = idx.ids_by_email.get(f.get("owner", ""))
            if owner:
                g.add_edge((NODE_PERSONA, owner), file_node, "drive")
            for token in _extract_projects(f.get("name", "")):
                g.add_edge(file_node, (NODE_PROJECT, token), "drive")
                if owner:
                    g.add_edge((NODE_PERSONA, owner), (NODE_PROJECT, token), "drive")

        return g


# Known project names used by generators. Anything matching one of these
# patterns is treated as a project reference.
_PROJECT_PATTERN = re.compile(
    r"\b(Atlas|Phoenix|pricing[- ]?redesign|pricing[- ]?page|mobile[- ]?v?\d*|"
    r"onboarding(?:[- ]?v?\d*)?|Q\d\s*(?:roadmap|planning|OKRs)?|roadmap|"
    r"Platform|Growth|Mobile\s+launch|Customer\s+Summit|churn[- ]?analysis|"
    r"infra[- ]?migration|API\s+deprecation|holiday\s+campaign|security\s+audit|"
    r"partner\s+agreement|board\s+deck|brand\s+refresh|data\s+warehouse|hiring\s+plan)\b",
    re.IGNORECASE,
)


def _extract_projects(text: str) -> set[str]:
    if not text:
        return set()
    return {m.group(0).lower() for m in _PROJECT_PATTERN.finditer(text)}


# ---------------------------------------------------------------------------
# Checks — each appends Violations to the report
# ---------------------------------------------------------------------------


def _check_gmail(workspace: dict[str, Any], idx: WorkspaceIndex, report: ConsistencyReport) -> None:
    gmail = workspace.get("gmail", {})
    for thread in gmail.get("threads", []):
        # Threads flagged as `external_sender=True` legitimately arrive from
        # outside the org (newsletters, automated alerts, phishing_like).
        # They never match a persona and would otherwise drown the report
        # in false-positive errors.
        is_external = bool(thread.get("external_sender"))
        for msg in thread.get("messages", []):
            sender = msg.get("from", "")
            if sender and sender not in idx.persona_emails and not is_external:
                report.violations.append(
                    Violation(
                        code="orphan_email_sender",
                        severity="error",
                        system="gmail",
                        message=f"Email sent by {sender}, but that email belongs to no persona.",
                        ref={
                            "thread_id": thread.get("id"),
                            "message_id": msg.get("id"),
                            "email": sender,
                        },
                    )
                )

            for recipient in msg.get("to", []) + msg.get("cc", []):
                if recipient and recipient not in idx.persona_emails:
                    report.violations.append(
                        Violation(
                            code="orphan_email_recipient",
                            severity="warning",
                            system="gmail",
                            message=f"Email sent to {recipient}, but that email belongs to no persona.",
                            ref={
                                "thread_id": thread.get("id"),
                                "message_id": msg.get("id"),
                                "email": recipient,
                            },
                        )
                    )

        # Reply timestamps must be monotonic
        timestamps = [_parse_ts(m.get("timestamp")) for m in thread.get("messages", [])]
        for i in range(1, len(timestamps)):
            if timestamps[i] is None or timestamps[i - 1] is None:
                continue
            if timestamps[i] < timestamps[i - 1]:
                report.violations.append(
                    Violation(
                        code="reply_before_original",
                        severity="error",
                        system="gmail",
                        message=f"Thread '{thread.get('subject')}' has a reply dated before the preceding message.",
                        ref={"thread_id": thread.get("id")},
                    )
                )
                break


def _check_slack(workspace: dict[str, Any], idx: WorkspaceIndex, report: ConsistencyReport) -> None:
    slack = workspace.get("slack", {})
    for ch in slack.get("channels", []):
        member_set = set(ch.get("members", []))
        for msg in ch.get("messages", []):
            uid = msg.get("user")
            if uid and uid not in idx.persona_ids:
                report.violations.append(
                    Violation(
                        code="orphan_slack_user",
                        severity="error",
                        system="slack",
                        message=f"Channel #{ch.get('name')} message authored by unknown user id '{uid}'.",
                        ref={
                            "channel": ch.get("name"),
                            "message_id": msg.get("id"),
                            "user_id": uid,
                        },
                    )
                )
            elif uid and uid not in member_set:
                report.violations.append(
                    Violation(
                        code="nonmember_posted",
                        severity="warning",
                        system="slack",
                        message=f"User {uid} posted in #{ch.get('name')} but is not listed as a member.",
                        ref={
                            "channel": ch.get("name"),
                            "message_id": msg.get("id"),
                            "user_id": uid,
                        },
                    )
                )

            # Mentions in the text must reference real slack handles
            for handle in re.findall(r"<@(@\w+)>", msg.get("text", "")):
                if handle not in idx.slack_handles:
                    report.violations.append(
                        Violation(
                            code="orphan_slack_mention",
                            severity="warning",
                            system="slack",
                            message=f"Message in #{ch.get('name')} @-mentions '{handle}', which is not a known handle.",
                            ref={
                                "channel": ch.get("name"),
                                "message_id": msg.get("id"),
                                "handle": handle,
                            },
                        )
                    )

    for dm in slack.get("dms", []):
        partner = dm.get("with")
        if partner and partner not in idx.persona_ids:
            report.violations.append(
                Violation(
                    code="orphan_dm_partner",
                    severity="error",
                    system="slack",
                    message=f"DM conversation with unknown user id '{partner}'.",
                    ref={"dm_id": dm.get("id"), "user_id": partner},
                )
            )


def _check_calendar(
    workspace: dict[str, Any], idx: WorkspaceIndex, report: ConsistencyReport
) -> None:
    cal = workspace.get("calendar", {})
    wh = cal.get("working_hours") or []
    wh_start, wh_end = (wh + [0, 24])[:2]

    for ev in cal.get("events", []):
        for attendee in ev.get("attendees", []):
            if attendee and attendee not in idx.persona_emails:
                report.violations.append(
                    Violation(
                        code="orphan_event_attendee",
                        severity="error",
                        system="calendar",
                        message=f"Event '{ev.get('title')}' has attendee {attendee} who is not a persona.",
                        ref={"event_id": ev.get("id"), "email": attendee},
                    )
                )

        organizer = ev.get("organizer")
        if organizer and organizer not in idx.persona_emails:
            report.violations.append(
                Violation(
                    code="orphan_event_organizer",
                    severity="error",
                    system="calendar",
                    message=f"Event '{ev.get('title')}' organized by non-persona {organizer}.",
                    ref={"event_id": ev.get("id"), "email": organizer},
                )
            )

        start = _parse_ts(ev.get("start"))
        end = _parse_ts(ev.get("end"))
        if start and end and end <= start:
            report.violations.append(
                Violation(
                    code="event_end_before_start",
                    severity="error",
                    system="calendar",
                    message=f"Event '{ev.get('title')}' ends before or at its start time.",
                    ref={"event_id": ev.get("id")},
                )
            )

        # Meetings outside working hours are a soft signal — interesting for
        # scenarios but worth flagging so generators can be tuned.
        if start and (start.hour < wh_start or start.hour >= wh_end):
            report.violations.append(
                Violation(
                    code="event_outside_working_hours",
                    severity="info",
                    system="calendar",
                    message=(
                        f"Event '{ev.get('title')}' at {start.isoformat()} falls outside "
                        f"the user's working hours ({wh_start}:00–{wh_end}:00)."
                    ),
                    ref={"event_id": ev.get("id")},
                )
            )


def _check_drive(workspace: dict[str, Any], idx: WorkspaceIndex, report: ConsistencyReport) -> None:
    drive = workspace.get("drive", {})
    for folder in drive.get("folders", []):
        parent = folder.get("parent_id")
        if parent and parent not in idx.folder_ids:
            report.violations.append(
                Violation(
                    code="orphan_folder_parent",
                    severity="error",
                    system="drive",
                    message=f"Folder '{folder.get('name')}' has parent_id '{parent}' which does not exist.",
                    ref={"folder_id": folder.get("id"), "parent_id": parent},
                )
            )

    for f in drive.get("files", []):
        parent = f.get("parent_id")
        if parent and parent not in idx.folder_ids:
            report.violations.append(
                Violation(
                    code="orphan_file_parent",
                    severity="error",
                    system="drive",
                    message=f"File '{f.get('name')}' has parent_id '{parent}' which does not exist.",
                    ref={"file_id": f.get("id"), "parent_id": parent},
                )
            )

        owner = f.get("owner")
        if owner and owner not in idx.persona_emails:
            report.violations.append(
                Violation(
                    code="orphan_file_owner",
                    severity="error",
                    system="drive",
                    message=f"File '{f.get('name')}' owned by non-persona {owner}.",
                    ref={"file_id": f.get("id"), "email": owner},
                )
            )

        modifier = f.get("modified_by")
        if modifier and modifier not in idx.persona_emails:
            report.violations.append(
                Violation(
                    code="orphan_file_modifier",
                    severity="warning",
                    system="drive",
                    message=f"File '{f.get('name')}' last modified by non-persona {modifier}.",
                    ref={"file_id": f.get("id"), "email": modifier},
                )
            )

        for collaborator in f.get("shared_with", []):
            if collaborator and collaborator not in idx.persona_emails:
                report.violations.append(
                    Violation(
                        code="orphan_file_collaborator",
                        severity="warning",
                        system="drive",
                        message=f"File '{f.get('name')}' shared with non-persona {collaborator}.",
                        ref={"file_id": f.get("id"), "email": collaborator},
                    )
                )

        created = _parse_ts(f.get("created"))
        modified = _parse_ts(f.get("modified"))
        if created and modified and modified < created:
            report.violations.append(
                Violation(
                    code="file_modified_before_created",
                    severity="error",
                    system="drive",
                    message=f"File '{f.get('name')}' has modified < created.",
                    ref={"file_id": f.get("id")},
                )
            )

        # File versions must stay inside the file's created..modified window
        # and be monotonically ordered by revision number.
        versions = f.get("versions") or []
        prev_ts: datetime | None = None
        for v in versions:
            v_ts = _parse_ts(v.get("timestamp"))
            if v_ts is None:
                continue
            if created and v_ts < created - timedelta(seconds=1):
                report.violations.append(
                    Violation(
                        code="version_before_file_created",
                        severity="error",
                        system="drive",
                        message=(
                            f"File '{f.get('name')}' has revision {v.get('revision')} "
                            f"dated {v_ts.isoformat()} before file creation."
                        ),
                        ref={"file_id": f.get("id"), "revision": v.get("revision")},
                    )
                )
            if modified and v_ts > modified + timedelta(seconds=1):
                report.violations.append(
                    Violation(
                        code="version_after_file_modified",
                        severity="error",
                        system="drive",
                        message=(
                            f"File '{f.get('name')}' has revision {v.get('revision')} "
                            f"dated {v_ts.isoformat()} after file's last modification."
                        ),
                        ref={"file_id": f.get("id"), "revision": v.get("revision")},
                    )
                )
            if prev_ts and v_ts < prev_ts:
                report.violations.append(
                    Violation(
                        code="version_timestamp_out_of_order",
                        severity="warning",
                        system="drive",
                        message=(
                            f"File '{f.get('name')}' versions are not monotonic: "
                            f"revision {v.get('revision')} goes backwards in time."
                        ),
                        ref={"file_id": f.get("id"), "revision": v.get("revision")},
                    )
                )
            author = v.get("author")
            if author and author not in idx.persona_emails:
                report.violations.append(
                    Violation(
                        code="orphan_version_author",
                        severity="warning",
                        system="drive",
                        message=f"File '{f.get('name')}' revision {v.get('revision')} authored by non-persona {author}.",
                        ref={
                            "file_id": f.get("id"),
                            "revision": v.get("revision"),
                            "email": author,
                        },
                    )
                )
            prev_ts = v_ts


def _check_drive_comments_and_activity(
    workspace: dict[str, Any],
    idx: WorkspaceIndex,
    report: ConsistencyReport,
) -> None:
    """Comments and activity log must reference real files and real personas."""
    drive = workspace.get("drive", {})
    file_ids = idx.file_ids

    for c in drive.get("comments", []):
        if c.get("file_id") not in file_ids:
            report.violations.append(
                Violation(
                    code="orphan_comment_file",
                    severity="error",
                    system="drive",
                    message=f"Comment {c.get('id')} references unknown file_id {c.get('file_id')}.",
                    ref={"comment_id": c.get("id"), "file_id": c.get("file_id")},
                )
            )
        author = c.get("author")
        if author and author not in idx.persona_emails:
            report.violations.append(
                Violation(
                    code="orphan_comment_author",
                    severity="warning",
                    system="drive",
                    message=f"Comment {c.get('id')} authored by non-persona {author}.",
                    ref={"comment_id": c.get("id"), "email": author},
                )
            )

    for a in drive.get("activity", []):
        if a.get("file_id") not in file_ids:
            report.violations.append(
                Violation(
                    code="orphan_activity_file",
                    severity="error",
                    system="drive",
                    message=f"Activity event {a.get('id')} references unknown file_id {a.get('file_id')}.",
                    ref={"activity_id": a.get("id"), "file_id": a.get("file_id")},
                )
            )
        actor = a.get("actor")
        if actor and actor not in idx.persona_emails:
            report.violations.append(
                Violation(
                    code="orphan_activity_actor",
                    severity="warning",
                    system="drive",
                    message=f"Activity event {a.get('id')} performed by non-persona {actor}.",
                    ref={"activity_id": a.get("id"), "email": actor},
                )
            )


def _check_whatsapp(
    workspace: dict[str, Any], idx: WorkspaceIndex, report: ConsistencyReport
) -> None:
    """WhatsApp reply-to targets must reference messages inside the same chat."""
    for chat in workspace.get("whatsapp", {}).get("chats", []):
        chat_id = chat.get("id", "")
        known_ids = idx.message_ids_by_chat.get(chat_id, set())
        for m in chat.get("messages", []):
            reply = m.get("reply_to")
            if not reply:
                continue
            target_id = reply.get("message_id")
            if target_id and target_id not in known_ids:
                report.violations.append(
                    Violation(
                        code="orphan_whatsapp_reply_target",
                        severity="warning",
                        system="whatsapp",
                        message=(
                            f"WhatsApp message {m.get('id')} in chat '{chat.get('name')}' "
                            f"replies to missing message {target_id}."
                        ),
                        ref={"chat_id": chat_id, "message_id": m.get("id"), "target_id": target_id},
                    )
                )


def _check_cross_system_projects(
    workspace: dict[str, Any],
    idx: WorkspaceIndex,
    graph: ReferenceGraph,
    report: ConsistencyReport,
) -> None:
    """Projects mentioned in Gmail/Slack should also appear somewhere in Drive or Calendar.

    A project that only lives inside one system is a weak scenario: an agent
    cannot reason across systems about it. The check now uses the derived
    reference graph so we can distinguish "project discussed only" from
    "project grounded somewhere concrete".
    """
    conversational_systems = {"gmail", "slack"}
    grounded_systems = {"calendar", "drive"}

    for node in graph.nodes_of_type(NODE_PROJECT):
        systems = graph.systems_for(node)
        if systems & conversational_systems and not systems & grounded_systems:
            report.violations.append(
                Violation(
                    code="project_without_artifact",
                    severity="warning",
                    system="cross",
                    message=(
                        f"Project '{node[1]}' is discussed in email/slack but has no "
                        f"corresponding Drive file or Calendar event."
                    ),
                    ref={"project": node[1]},
                )
            )


def _check_persona_network_coverage(
    workspace: dict[str, Any],
    idx: WorkspaceIndex,
    graph: ReferenceGraph,
    report: ConsistencyReport,
) -> None:
    """Every persona should touch at least one communication system.

    A persona that exists in `personas.json` but never appears as a sender,
    recipient, channel member, event attendee, or file owner is dead weight
    — scenarios built against them won't have any grounding. Flagged as
    info because small workspaces can legitimately include "background"
    personas with no activity.
    """
    active_systems = {"gmail", "slack", "calendar", "drive"}
    for node in graph.nodes_of_type(NODE_PERSONA):
        pid = node[1]
        if pid == idx.user_id:
            continue
        systems = graph.systems_for(node)
        if not systems & active_systems:
            report.violations.append(
                Violation(
                    code="persona_never_referenced",
                    severity="info",
                    system="cross",
                    message=(
                        f"Persona {pid} ({idx.emails_by_persona.get(pid, '?')}) is "
                        f"defined but never appears in gmail/slack/calendar/drive."
                    ),
                    ref={"persona_id": pid},
                )
            )


# ---------------------------------------------------------------------------
# Repair — idempotent, best-effort fixups for non-semantic orphan references
# ---------------------------------------------------------------------------


def _repair_orphans(
    workspace: dict[str, Any], idx: WorkspaceIndex, report: ConsistencyReport
) -> None:
    """Rewrite clearly-broken references to point at valid personas / folders.

    We only repair reference integrity issues where the fix is mechanical
    (e.g. non-persona email → user's email). Semantic issues like
    `project_without_artifact` are handled by a separate repair pass that
    can synthesise minimal new content to close the gap.
    """

    persona_emails = list(idx.persona_emails)
    if not persona_emails:
        return
    fallback_email = idx.user_email or persona_emails[0]

    # Drive: owner / modified_by / shared_with
    for f in workspace.get("drive", {}).get("files", []):
        if f.get("owner") and f["owner"] not in idx.persona_emails:
            bad = f["owner"]
            f["owner"] = fallback_email
            report.repaired.append(
                Violation(
                    code="orphan_file_owner",
                    severity="error",
                    system="drive",
                    message=f"Rewrote orphan owner {bad} to {fallback_email}.",
                    ref={"file_id": f.get("id")},
                )
            )
        if f.get("modified_by") and f["modified_by"] not in idx.persona_emails:
            bad = f["modified_by"]
            f["modified_by"] = fallback_email
            report.repaired.append(
                Violation(
                    code="orphan_file_modifier",
                    severity="warning",
                    system="drive",
                    message=f"Rewrote orphan modifier {bad} to {fallback_email}.",
                    ref={"file_id": f.get("id")},
                )
            )
        cleaned = [e for e in f.get("shared_with", []) if e in idx.persona_emails]
        if len(cleaned) != len(f.get("shared_with", [])):
            f["shared_with"] = cleaned

        # Version authors: reassign orphans to the user so the revision
        # history stays plausible rather than just shrugging them off.
        for v in f.get("versions", []) or []:
            if v.get("author") and v["author"] not in idx.persona_emails:
                bad = v["author"]
                v["author"] = fallback_email
                report.repaired.append(
                    Violation(
                        code="orphan_version_author",
                        severity="warning",
                        system="drive",
                        message=f"Rewrote orphan revision author {bad} to {fallback_email}.",
                        ref={"file_id": f.get("id"), "revision": v.get("revision")},
                    )
                )

    # Folders with orphan parents: reparent to root-shared if present, else None
    shared_root = next(
        (
            fd["id"]
            for fd in workspace.get("drive", {}).get("folders", [])
            if fd.get("name") == "Team Shared" and fd.get("parent_id") is None
        ),
        None,
    )
    for fd in workspace.get("drive", {}).get("folders", []):
        if fd.get("parent_id") and fd["parent_id"] not in idx.folder_ids:
            fd["parent_id"] = shared_root
    for f in workspace.get("drive", {}).get("files", []):
        if f.get("parent_id") and f["parent_id"] not in idx.folder_ids:
            f["parent_id"] = shared_root

    # Drive comments and activity events: drop ones pointing at unknown files
    # (dangling), rewrite orphan authors/actors to the user.
    drive = workspace.setdefault("drive", {})
    kept_comments = []
    for c in drive.get("comments", []) or []:
        if c.get("file_id") not in idx.file_ids:
            continue  # silently drop; the check layer already recorded the violation
        if c.get("author") and c["author"] not in idx.persona_emails:
            bad = c["author"]
            c["author"] = fallback_email
            report.repaired.append(
                Violation(
                    code="orphan_comment_author",
                    severity="warning",
                    system="drive",
                    message=f"Rewrote orphan comment author {bad} to {fallback_email}.",
                    ref={"comment_id": c.get("id")},
                )
            )
        kept_comments.append(c)
    drive["comments"] = kept_comments

    kept_activity = []
    for a in drive.get("activity", []) or []:
        if a.get("file_id") not in idx.file_ids:
            continue
        if a.get("actor") and a["actor"] not in idx.persona_emails:
            bad = a["actor"]
            a["actor"] = fallback_email
            report.repaired.append(
                Violation(
                    code="orphan_activity_actor",
                    severity="warning",
                    system="drive",
                    message=f"Rewrote orphan activity actor {bad} to {fallback_email}.",
                    ref={"activity_id": a.get("id")},
                )
            )
        kept_activity.append(a)
    drive["activity"] = kept_activity

    # Calendar attendees / organizers → drop orphans, fall back to user
    for ev in workspace.get("calendar", {}).get("events", []):
        ev["attendees"] = [a for a in ev.get("attendees", []) if a in idx.persona_emails]
        if ev.get("organizer") and ev["organizer"] not in idx.persona_emails:
            ev["organizer"] = fallback_email

    # Gmail sender/recipients: drop CCs that don't exist, leave errors for
    # report-only handling (changing sender identity is a semantic change).
    for thread in workspace.get("gmail", {}).get("threads", []):
        for msg in thread.get("messages", []):
            msg["to"] = [e for e in msg.get("to", []) if e in idx.persona_emails] or [
                fallback_email
            ]
            msg["cc"] = [e for e in msg.get("cc", []) if e in idx.persona_emails]

    # Slack: drop orphan members, drop messages from unknown users
    for ch in workspace.get("slack", {}).get("channels", []):
        ch["members"] = [m for m in ch.get("members", []) if m in idx.persona_ids]
        ch["messages"] = [m for m in ch.get("messages", []) if m.get("user") in idx.persona_ids]
    workspace.get("slack", {})["dms"] = [
        dm for dm in workspace.get("slack", {}).get("dms", []) if dm.get("with") in idx.persona_ids
    ]

    # WhatsApp: drop reply-to pointers that lead nowhere inside the chat.
    for chat in workspace.get("whatsapp", {}).get("chats", []):
        chat_id = chat.get("id", "")
        known = idx.message_ids_by_chat.get(chat_id, set())
        for m in chat.get("messages", []):
            reply = m.get("reply_to")
            if reply and reply.get("message_id") not in known:
                m.pop("reply_to", None)
                report.repaired.append(
                    Violation(
                        code="orphan_whatsapp_reply_target",
                        severity="warning",
                        system="whatsapp",
                        message=(
                            f"Dropped dangling reply pointer in chat '{chat.get('name')}' "
                            f"message {m.get('id')}."
                        ),
                        ref={"chat_id": chat_id, "message_id": m.get("id")},
                    )
                )


def _repair_project_coverage(
    workspace: dict[str, Any],
    idx: WorkspaceIndex,
    report: ConsistencyReport,
) -> None:
    """Close `project_without_artifact` warnings by planting a stub Drive file.

    Strategy:
      - Rebuild the reference graph to get an up-to-date coverage view.
      - For each project that appears in gmail/slack but nowhere in drive
        or calendar, synthesise a single "{Project} — Working Notes" doc in
        a plausible project folder (falling back to Team Shared) owned by
        the most active persona mentioning the project.
      - Record a repaired Violation so callers can audit what changed.

    Repair is capped at a reasonable number of new files per invocation so
    a degenerate workspace doesn't explode. The cap is generous (50) — real
    generators produce at most a handful of uncovered projects.
    """
    graph = ReferenceGraph.build(workspace, idx)

    conversational_systems = {"gmail", "slack"}
    grounded_systems = {"calendar", "drive"}

    uncovered: list[str] = []
    for node in graph.nodes_of_type(NODE_PROJECT):
        systems = graph.systems_for(node)
        if systems & conversational_systems and not systems & grounded_systems:
            uncovered.append(node[1])

    if not uncovered:
        return

    drive = workspace.setdefault("drive", {})
    folders = drive.setdefault("folders", [])
    files = drive.setdefault("files", [])

    # Shared root fallback
    shared_root_id = next(
        (f["id"] for f in folders if f.get("name") == "Team Shared" and f.get("parent_id") is None),
        None,
    )

    # Project folder lookup is case-insensitive on name against the token.
    folder_by_project: dict[str, dict[str, Any]] = {}
    for f in folders:
        if f.get("parent_id") == shared_root_id:
            folder_by_project[f.get("name", "").lower()] = f

    # Who mentions each project most? Use that as the plausible owner.
    mention_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for thread in workspace.get("gmail", {}).get("threads", []):
        for msg in thread.get("messages", []):
            sender = msg.get("from", "")
            if sender not in idx.persona_emails:
                continue
            tokens = _extract_projects(thread.get("subject", "")) | _extract_projects(
                msg.get("body", "")
            )
            for t in tokens:
                mention_counter[t][sender] += 1
    for ch in workspace.get("slack", {}).get("channels", []):
        for m in ch.get("messages", []):
            uid = m.get("user")
            if uid not in idx.persona_ids:
                continue
            email = idx.emails_by_persona.get(uid)
            if not email:
                continue
            for t in _extract_projects(m.get("text", "")):
                mention_counter[t][email] += 1

    now = datetime.now()
    created_count = 0
    cap = 50
    for project_token in uncovered:
        if created_count >= cap:
            break

        # Pick parent folder: exact project folder if we have one, else
        # Team Shared, else the first folder available, else skip.
        parent = folder_by_project.get(project_token)
        parent_id = (
            parent["id"]
            if parent
            else shared_root_id
            if shared_root_id
            else (folders[0]["id"] if folders else None)
        )
        if parent_id is None:
            continue

        owner_candidates = mention_counter.get(project_token, {})
        if owner_candidates:
            owner_email = max(owner_candidates.items(), key=lambda kv: kv[1])[0]
        else:
            owner_email = idx.user_email or next(iter(idx.persona_emails), "")
        if not owner_email:
            continue

        # Title-case the token for the file name so it reads like a real doc.
        display_name = project_token.strip()
        if display_name and display_name[0].islower():
            display_name = display_name[0].upper() + display_name[1:]

        file_id = f"file_repair_{uuid4().hex[:8]}"
        created_iso = (now - timedelta(days=7)).isoformat()
        modified_iso = now.isoformat()
        files.append(
            {
                "id": file_id,
                "name": f"{display_name} — Working Notes",
                "type": "doc",
                "parent_id": parent_id,
                "owner": owner_email,
                "shared_with": sorted(owner_candidates.keys())[:5] or [idx.user_email]
                if idx.user_email
                else [],
                "created": created_iso,
                "modified": modified_iso,
                "modified_by": owner_email,
                "size_kb": 12,
                "starred": False,
                "comments": 0,
                "comment_count": 0,
                "unresolved_comment_count": 0,
                "version_count": 1,
                "versions": [
                    {
                        "id": f"rev_repair_{uuid4().hex[:8]}",
                        "file_id": file_id,
                        "revision": 1,
                        "author": owner_email,
                        "summary": "stub created to ground cross-system references",
                        "timestamp": created_iso,
                        "size_kb_delta": 12,
                    }
                ],
                "synthesised_by_repair": True,
            }
        )
        created_count += 1

        report.repaired.append(
            Violation(
                code="project_without_artifact",
                severity="warning",
                system="cross",
                message=(
                    f"Created stub Drive file '{display_name} — Working Notes' "
                    f"owned by {owner_email} to ground project '{project_token}'."
                ),
                ref={"project": project_token, "file_id": file_id},
            )
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check(workspace: dict[str, Any]) -> ConsistencyReport:
    """Run every consistency check and return a report (no mutation)."""
    idx = WorkspaceIndex.build(workspace)
    graph = ReferenceGraph.build(workspace, idx)
    report = ConsistencyReport()
    _check_gmail(workspace, idx, report)
    _check_slack(workspace, idx, report)
    _check_calendar(workspace, idx, report)
    _check_drive(workspace, idx, report)
    _check_drive_comments_and_activity(workspace, idx, report)
    _check_whatsapp(workspace, idx, report)
    _check_cross_system_projects(workspace, idx, graph, report)
    _check_persona_network_coverage(workspace, idx, graph, report)
    report.violations.sort(key=lambda v: (SEVERITY_ORDER.get(v.severity, 99), v.system, v.code))
    return report


def repair(workspace: dict[str, Any]) -> tuple[dict[str, Any], ConsistencyReport]:
    """Run checks, apply mechanical repairs, then re-check.

    Returns the (mutated) workspace and a report containing both repair
    actions and any remaining violations after the repair pass. The repair
    sequence is: reference-orphan rewrites → graph-driven project coverage
    stubs → re-check.
    """
    idx = WorkspaceIndex.build(workspace)
    report = ConsistencyReport()
    _repair_orphans(workspace, idx, report)

    # Rebuild the index after the orphan pass so downstream repairs see the
    # cleaned state (dropped comments, retargeted owners, etc).
    idx = WorkspaceIndex.build(workspace)
    _repair_project_coverage(workspace, idx, report)

    # Final check reflects the post-repair reality.
    final = check(workspace)
    final.repaired = report.repaired
    return workspace, final


def build_reference_graph(workspace: dict[str, Any]) -> ReferenceGraph:
    """Public helper: expose the cross-system graph for callers that want to
    build their own checks or visualise coverage externally."""
    idx = WorkspaceIndex.build(workspace)
    return ReferenceGraph.build(workspace, idx)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
