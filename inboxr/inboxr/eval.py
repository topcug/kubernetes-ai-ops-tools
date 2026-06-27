"""Evaluation harness — runs an agent against a scenario and scores it.

Pipeline:
    scenario -> Observation
    loop:
        agent.act(observation) -> AgentAction
        tools.apply(action)    -> new observation (+ trajectory entry)
        stop when agent returns final_answer or max_steps reached
    Rubric.score(trajectory, scenario) -> EvalResult

Agents are pluggable. A MockAgent is provided so the harness is testable
without API keys. OpenAI and Anthropic adapters are imported lazily so the
core package has no hard dependency on either SDK.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

import click

# ---------------------------------------------------------------------------
# Small helpers used by WorkspaceTools
# ---------------------------------------------------------------------------


def _safe_iso(value: Any) -> datetime | None:
    """Best-effort ISO timestamp parse — returns None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _in_window(event: dict[str, Any], frm: datetime, to: datetime) -> bool:
    """True if an event overlaps the half-open window [frm, to)."""
    s = _safe_iso(event.get("start"))
    e = _safe_iso(event.get("end"))
    if s is None or e is None:
        return False
    return s < to and e > frm


def _thread_preview(thread: dict[str, Any]) -> dict[str, Any]:
    """Uniform compact view of a thread used by list/search result sets."""
    first = (thread.get("messages") or [{}])[0]
    last = (thread.get("messages") or [{}])[-1]
    return {
        "id": thread.get("id"),
        "subject": thread.get("subject"),
        "from": first.get("from"),
        "unread": thread.get("unread"),
        "labels": thread.get("labels", []),
        "last_timestamp": last.get("timestamp"),
    }


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass
class AgentAction:
    """One step produced by an agent."""

    thought: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None  # non-None => agent is done

    def is_terminal(self) -> bool:
        return self.final_answer is not None


@dataclass
class TrajectoryStep:
    """A single observation-action-observation transition."""

    step: int
    thought: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    final_answer: str | None = None


@dataclass
class EvalResult:
    scenario_id: str
    template: str
    agent_name: str
    trajectory: list[TrajectoryStep]
    criteria_scores: list[dict[str, Any]]  # {criterion, passed, justification}
    score: float  # passed / total
    final_answer: str
    stopped_reason: str  # "terminal" | "max_steps" | "error"
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "template": self.template,
            "agent_name": self.agent_name,
            "score": self.score,
            "stopped_reason": self.stopped_reason,
            "final_answer": self.final_answer,
            "criteria_scores": self.criteria_scores,
            "trajectory": [asdict(s) for s in self.trajectory],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def summary(self) -> str:
        lines = [
            f"Agent:    {self.agent_name}",
            f"Scenario: {self.template} ({self.scenario_id})",
            f"Steps:    {len(self.trajectory)}  ({self.stopped_reason})",
            f"Score:    {self.score:.2f}  ({sum(1 for c in self.criteria_scores if c['passed'])}/{len(self.criteria_scores)})",
            "",
            "Criteria:",
        ]
        for c in self.criteria_scores:
            mark = "PASS" if c["passed"] else "FAIL"
            lines.append(f"  [{mark}] {c['criterion']}")
            if c.get("justification"):
                lines.append(f"         {c['justification']}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools exposed to the agent
# ---------------------------------------------------------------------------


class WorkspaceTools:
    """Read-only (plus drafts and sim-actions) view of a scenario workspace.

    Every call returns a compact JSON-serializable result. Mutating tools fall
    into two classes:

    - `draft_*` tools never touch the workspace; they append to `drafts` so
      the rubric can score what the agent produced.
    - `sim_*` actions (send_email, create_calendar_event, archive, share_file,
      set_oof, etc.) append to `actions` — a parallel log — and *also* apply
      a best-effort local mutation so subsequent tool calls see consistent
      state (e.g. archiving then listing labels shows the new ARCHIVED tag).

    Scenarios remain deterministic because every mutation is bounded and
    reversible: no network, no real API, no hidden side effects.
    """

    def __init__(self, workspace: dict[str, Any]) -> None:
        self.workspace = workspace
        self.drafts: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []  # chronological log of sim_* calls

    # --- Schema exposed to the agent ---------------------------------------

    SPEC: list[dict[str, Any]] = [
        # --- Read: Gmail ---------------------------------------------------
        {
            "name": "list_emails",
            "description": "List email threads, newest first. Optional filter by label or unread-only.",
            "params": {"label": "str?", "unread_only": "bool?", "limit": "int?"},
        },
        {
            "name": "read_email",
            "description": "Read the full body of one email thread by id.",
            "params": {"thread_id": "str"},
        },
        {
            "name": "search_emails",
            "description": "Full-text search email subjects and bodies. Case-insensitive.",
            "params": {"query": "str", "limit": "int?"},
        },
        # --- Read: Calendar ------------------------------------------------
        {
            "name": "list_calendar",
            "description": "List calendar events in chronological order, with conflict markers.",
            "params": {"limit": "int?"},
        },
        {
            "name": "find_free_slots",
            "description": "Return free time slots on the user's calendar within [from_iso, to_iso], each at least duration_minutes long.",
            "params": {"from_iso": "str", "to_iso": "str", "duration_minutes": "int"},
        },
        # --- Read: Slack ---------------------------------------------------
        {
            "name": "list_slack_mentions",
            "description": "List Slack messages where the user was @-mentioned.",
            "params": {},
        },
        {
            "name": "list_slack_channels",
            "description": "List Slack channels visible to the user, with recent activity counts.",
            "params": {},
        },
        {
            "name": "read_slack_channel",
            "description": "Read the most recent messages in a Slack channel by name.",
            "params": {"channel": "str", "limit": "int?"},
        },
        {
            "name": "search_slack",
            "description": "Case-insensitive search of all channel + DM text.",
            "params": {"query": "str", "limit": "int?"},
        },
        {
            "name": "list_dms",
            "description": "List direct-message conversations in recency order.",
            "params": {},
        },
        {
            "name": "read_dm",
            "description": "Read the messages of a single direct-message conversation by id.",
            "params": {"dm_id": "str", "limit": "int?"},
        },
        # --- Read: Drive ---------------------------------------------------
        {
            "name": "search_drive",
            "description": "Search Drive file names for a substring. Case-insensitive.",
            "params": {"query": "str"},
        },
        {
            "name": "read_file_metadata",
            "description": "Return metadata (name, owner, folder, version count, comment count) for one file.",
            "params": {"file_id": "str"},
        },
        {
            "name": "list_file_versions",
            "description": "Return the revision history of a file with author and summary per revision.",
            "params": {"file_id": "str"},
        },
        {
            "name": "list_file_comments",
            "description": "Return comment threads on a file. Optionally only unresolved.",
            "params": {"file_id": "str", "unresolved_only": "bool?"},
        },
        # --- Read: People --------------------------------------------------
        {
            "name": "search_people",
            "description": "Search personas by name, role, or department.",
            "params": {"query": "str"},
        },
        {
            "name": "get_persona",
            "description": "Fetch one persona's profile + relationship history by id or email.",
            "params": {"who": "str"},
        },
        # --- Draft (no mutation) ------------------------------------------
        {
            "name": "draft_email_reply",
            "description": "Draft a reply to an email thread (recorded; no real send).",
            "params": {"thread_id": "str", "body": "str"},
        },
        {
            "name": "draft_message",
            "description": "Draft a free-form message for later review (reschedule note, status update, etc.).",
            "params": {"to": "str", "channel": "str", "body": "str"},
        },
        # --- Simulated actions (mutate local workspace state) -------------
        {
            "name": "send_email",
            "description": "Simulate sending a new email. Appends a SENT thread locally.",
            "params": {"to": "list[str]", "subject": "str", "body": "str", "cc": "list[str]?"},
        },
        {
            "name": "reply_in_thread",
            "description": "Simulate replying inline inside an existing thread.",
            "params": {"thread_id": "str", "body": "str"},
        },
        {
            "name": "forward_email",
            "description": "Simulate forwarding a thread to one or more people.",
            "params": {"thread_id": "str", "to": "list[str]", "note": "str?"},
        },
        {
            "name": "archive_email",
            "description": "Move a thread out of INBOX into ARCHIVED.",
            "params": {"thread_id": "str"},
        },
        {
            "name": "star_email",
            "description": "Add the STARRED label to a thread.",
            "params": {"thread_id": "str"},
        },
        {
            "name": "add_label",
            "description": "Attach an arbitrary label to a thread.",
            "params": {"thread_id": "str", "label": "str"},
        },
        {
            "name": "mark_read",
            "description": "Mark a thread as read.",
            "params": {"thread_id": "str"},
        },
        {
            "name": "create_calendar_event",
            "description": "Simulate creating a new event on the user's calendar.",
            "params": {
                "title": "str",
                "start_iso": "str",
                "end_iso": "str",
                "attendees": "list[str]",
            },
        },
        {
            "name": "reschedule_event",
            "description": "Change the start/end of an existing event.",
            "params": {"event_id": "str", "new_start_iso": "str", "new_end_iso": "str"},
        },
        {
            "name": "schedule_meeting_with_attendees",
            "description": "Find a slot and create a meeting with the given attendees, duration, and window.",
            "params": {
                "attendees": "list[str]",
                "duration_minutes": "int",
                "from_iso": "str",
                "to_iso": "str",
                "title": "str",
            },
        },
        {
            "name": "send_slack_message",
            "description": "Simulate posting a message to a Slack channel.",
            "params": {"channel": "str", "body": "str"},
        },
        {
            "name": "send_dm",
            "description": "Simulate sending a direct message to a persona.",
            "params": {"to": "str", "body": "str"},
        },
        {
            "name": "react_slack",
            "description": "Add a reaction emoji to an existing Slack message.",
            "params": {"message_id": "str", "emoji": "str"},
        },
        {
            "name": "share_file",
            "description": "Share a Drive file with a persona.",
            "params": {"file_id": "str", "with": "str"},
        },
        {
            "name": "comment_on_file",
            "description": "Post a comment on a Drive file at a given anchor.",
            "params": {"file_id": "str", "body": "str", "anchor": "str?"},
        },
        {
            "name": "set_out_of_office",
            "description": "Turn on an OOO auto-reply within a window.",
            "params": {"from_iso": "str", "to_iso": "str", "message": "str"},
        },
    ]

    # --- Dispatch ----------------------------------------------------------

    def apply(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        name = tool_call.get("name", "")
        args = tool_call.get("arguments", {}) or {}
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            return {"error": f"unknown tool: {name}"}
        try:
            return handler(**args)
        except TypeError as e:
            return {"error": f"bad arguments for {name}: {e}"}

    # --- Internal helpers --------------------------------------------------

    def _user_email(self) -> str:
        return self.workspace.get("meta", {}).get("user_email", "")

    def _find_thread(self, thread_id: str) -> dict[str, Any] | None:
        for t in self.workspace.get("gmail", {}).get("threads", []):
            if t.get("id") == thread_id:
                return t
        return None

    def _find_event(self, event_id: str) -> dict[str, Any] | None:
        for e in self.workspace.get("calendar", {}).get("events", []):
            if e.get("id") == event_id:
                return e
        return None

    def _find_file(self, file_id: str) -> dict[str, Any] | None:
        for f in self.workspace.get("drive", {}).get("files", []):
            if f.get("id") == file_id:
                return f
        return None

    def _find_persona(self, who: str) -> dict[str, Any] | None:
        for p in self.workspace.get("personas", []):
            if p.get("id") == who or p.get("email") == who:
                return p
            if who and who.lower() == (p.get("name") or "").lower():
                return p
        return None

    def _record(self, kind: str, **fields: Any) -> dict[str, Any]:
        entry = {"kind": kind, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
        self.actions.append(entry)
        return entry

    # --- Read-side tools (non-mutating) -----------------------------------

    def _t_list_emails(
        self, label: str | None = None, unread_only: bool = False, limit: int = 25
    ) -> dict[str, Any]:
        threads = self.workspace.get("gmail", {}).get("threads", [])
        out = []
        for t in threads:
            if label and label not in t.get("labels", []):
                continue
            if unread_only and not t.get("unread"):
                continue
            out.append(
                {
                    "id": t.get("id"),
                    "subject": t.get("subject"),
                    "from": t.get("messages", [{}])[0].get("from"),
                    "unread": t.get("unread"),
                    "labels": t.get("labels", []),
                    "last_timestamp": t.get("messages", [{}])[-1].get("timestamp"),
                }
            )
            if len(out) >= limit:
                break
        return {"threads": out, "count": len(out)}

    def _t_read_email(self, thread_id: str) -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        return {
            "id": t["id"],
            "subject": t.get("subject"),
            "labels": t.get("labels", []),
            "messages": [
                {k: v for k, v in m.items() if k != "kind_hint"} for m in t.get("messages", [])
            ],
        }

    def _t_search_emails(self, query: str, limit: int = 20) -> dict[str, Any]:
        q = (query or "").lower()
        if not q:
            return {"threads": [], "count": 0}
        out = []
        for t in self.workspace.get("gmail", {}).get("threads", []):
            if q in (t.get("subject", "") or "").lower():
                out.append(_thread_preview(t))
                if len(out) >= limit:
                    break
                continue
            for m in t.get("messages", []):
                if q in (m.get("body", "") or "").lower():
                    out.append(_thread_preview(t))
                    break
            if len(out) >= limit:
                break
        return {"threads": out, "count": len(out)}

    def _t_list_calendar(self, limit: int = 50) -> dict[str, Any]:
        cal = self.workspace.get("calendar", {})
        events = cal.get("events", [])[:limit]
        conflict_ids = set()
        for c in cal.get("conflicts", []):
            conflict_ids.add(c["event_a"])
            conflict_ids.add(c["event_b"])
        return {
            "events": [
                {
                    "id": e.get("id"),
                    "title": e.get("title"),
                    "start": e.get("start"),
                    "end": e.get("end"),
                    "attendees": e.get("attendees", []),
                    "conflict": e.get("id") in conflict_ids,
                }
                for e in events
            ],
        }

    def _t_find_free_slots(
        self, from_iso: str, to_iso: str, duration_minutes: int
    ) -> dict[str, Any]:
        """Return gaps between events inside [from, to] that are long enough.

        Granularity is one-minute; the helper sorts existing events by start
        time, walks the timeline, and emits every window >= duration.
        """
        try:
            frm = datetime.fromisoformat(from_iso)
            to = datetime.fromisoformat(to_iso)
        except ValueError as e:
            return {"error": f"bad iso timestamp: {e}"}
        if to <= frm:
            return {"error": "to_iso must be after from_iso"}

        events = sorted(
            (
                e
                for e in self.workspace.get("calendar", {}).get("events", [])
                if _in_window(e, frm, to)
            ),
            key=lambda e: e.get("start", ""),
        )
        dur = timedelta(minutes=duration_minutes)

        free: list[dict[str, str]] = []
        cursor = frm
        for ev in events:
            ev_start = _safe_iso(ev.get("start"))
            ev_end = _safe_iso(ev.get("end"))
            if ev_start is None:
                continue
            if ev_start - cursor >= dur:
                free.append({"start": cursor.isoformat(), "end": ev_start.isoformat()})
            cursor = max(cursor, ev_end or ev_start)
        if to - cursor >= dur:
            free.append({"start": cursor.isoformat(), "end": to.isoformat()})
        return {"slots": free, "count": len(free)}

    def _t_list_slack_mentions(self) -> dict[str, Any]:
        return {"mentions": self.workspace.get("slack", {}).get("mentions", [])}

    def _t_list_slack_channels(self) -> dict[str, Any]:
        chans = []
        for ch in self.workspace.get("slack", {}).get("channels", []):
            chans.append(
                {
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "topic": ch.get("topic"),
                    "is_private": ch.get("is_private", False),
                    "member_count": len(ch.get("members", [])),
                    "message_count": len(ch.get("messages", [])),
                    "unread_count": ch.get("unread_count", 0),
                }
            )
        return {"channels": chans}

    def _t_read_slack_channel(self, channel: str, limit: int = 20) -> dict[str, Any]:
        """Return the `limit` most recent messages in a channel.

        Slack surfaces newest-first in the UI; planted fixtures can have
        timestamps anywhere in the channel's history. Sort by timestamp
        descending and then slice so an agent reliably sees the most recent
        N — not simply the tail of the underlying list.
        """
        for ch in self.workspace.get("slack", {}).get("channels", []):
            if ch.get("name") == channel:
                sorted_msgs = sorted(
                    ch.get("messages", []),
                    key=lambda m: m.get("timestamp", ""),
                    reverse=True,
                )
                msgs = sorted_msgs[:limit]
                return {
                    "name": ch.get("name"),
                    "topic": ch.get("topic"),
                    "messages": [
                        {
                            "id": m.get("id"),
                            "from": m.get("user_name"),
                            "text": m.get("text"),
                            "timestamp": m.get("timestamp"),
                        }
                        for m in msgs
                    ],
                }
        return {"error": f"channel not found: {channel}"}

    def _t_search_slack(self, query: str, limit: int = 20) -> dict[str, Any]:
        q = (query or "").lower()
        hits: list[dict[str, Any]] = []
        if not q:
            return {"messages": [], "count": 0}
        for ch in self.workspace.get("slack", {}).get("channels", []):
            for m in ch.get("messages", []):
                if q in (m.get("text") or "").lower():
                    hits.append(
                        {
                            "scope": f"#{ch.get('name')}",
                            "from": m.get("user_name"),
                            "text": m.get("text"),
                            "timestamp": m.get("timestamp"),
                        }
                    )
                    if len(hits) >= limit:
                        return {"messages": hits, "count": len(hits)}
        for dm in self.workspace.get("slack", {}).get("dms", []):
            for m in dm.get("messages", []):
                if q in (m.get("text") or "").lower():
                    hits.append(
                        {
                            "scope": f"dm:{dm.get('with_name')}",
                            "from": m.get("user_name"),
                            "text": m.get("text"),
                            "timestamp": m.get("timestamp"),
                        }
                    )
                    if len(hits) >= limit:
                        return {"messages": hits, "count": len(hits)}
        return {"messages": hits, "count": len(hits)}

    def _t_list_dms(self) -> dict[str, Any]:
        dms = []
        for dm in self.workspace.get("slack", {}).get("dms", []):
            dms.append(
                {
                    "id": dm.get("id"),
                    "with": dm.get("with_name"),
                    "unread": dm.get("unread", False),
                    "message_count": len(dm.get("messages", [])),
                }
            )
        return {"dms": dms}

    def _t_read_dm(self, dm_id: str, limit: int = 30) -> dict[str, Any]:
        for dm in self.workspace.get("slack", {}).get("dms", []):
            if dm.get("id") == dm_id:
                msgs = dm.get("messages", [])[-limit:]
                return {
                    "id": dm_id,
                    "with": dm.get("with_name"),
                    "messages": [
                        {
                            "id": m.get("id"),
                            "from": m.get("user_name"),
                            "text": m.get("text"),
                            "timestamp": m.get("timestamp"),
                        }
                        for m in msgs
                    ],
                }
        return {"error": f"dm not found: {dm_id}"}

    def _t_search_drive(self, query: str) -> dict[str, Any]:
        q = (query or "").lower()
        out = []
        for f in self.workspace.get("drive", {}).get("files", []):
            if q in f.get("name", "").lower():
                out.append(
                    {
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "owner": f.get("owner"),
                        "modified": f.get("modified"),
                    }
                )
        return {"files": out, "count": len(out)}

    def _t_read_file_metadata(self, file_id: str) -> dict[str, Any]:
        f = self._find_file(file_id)
        if not f:
            return {"error": f"file not found: {file_id}"}
        return {
            "id": f.get("id"),
            "name": f.get("name"),
            "type": f.get("type"),
            "parent_id": f.get("parent_id"),
            "owner": f.get("owner"),
            "shared_with": f.get("shared_with", []),
            "created": f.get("created"),
            "modified": f.get("modified"),
            "modified_by": f.get("modified_by"),
            "size_kb": f.get("size_kb"),
            "version_count": f.get("version_count", 0),
            "comment_count": f.get("comment_count", 0),
            "unresolved_comment_count": f.get("unresolved_comment_count", 0),
        }

    def _t_list_file_versions(self, file_id: str) -> dict[str, Any]:
        f = self._find_file(file_id)
        if not f:
            return {"error": f"file not found: {file_id}"}
        return {"versions": f.get("versions", [])}

    def _t_list_file_comments(self, file_id: str, unresolved_only: bool = False) -> dict[str, Any]:
        cms = [
            c
            for c in self.workspace.get("drive", {}).get("comments", [])
            if c.get("file_id") == file_id
        ]
        if unresolved_only:
            cms = [c for c in cms if not c.get("resolved")]
        return {"comments": cms, "count": len(cms)}

    def _t_search_people(self, query: str) -> dict[str, Any]:
        q = (query or "").lower()
        out = []
        for p in self.workspace.get("personas", []):
            hay = " ".join(
                [
                    str(p.get("name", "")),
                    str(p.get("role", "")),
                    str(p.get("department", "")),
                    str(p.get("email", "")),
                ]
            ).lower()
            if q and q in hay:
                out.append(
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "email": p.get("email"),
                        "role": p.get("role"),
                        "department": p.get("department"),
                    }
                )
        return {"people": out, "count": len(out)}

    def _t_get_persona(self, who: str) -> dict[str, Any]:
        p = self._find_persona(who)
        if not p:
            return {"error": f"persona not found: {who}"}
        return p

    # --- Draft tools (non-mutating) ---------------------------------------

    def _t_draft_email_reply(self, thread_id: str, body: str) -> dict[str, Any]:
        self.drafts.append({"kind": "email_reply", "thread_id": thread_id, "body": body})
        return {"ok": True, "draft_index": len(self.drafts) - 1}

    def _t_draft_message(self, to: str = "", channel: str = "", body: str = "") -> dict[str, Any]:
        self.drafts.append({"kind": "message", "to": to, "channel": channel, "body": body})
        return {"ok": True, "draft_index": len(self.drafts) - 1}

    # --- Simulated actions (mutating) -------------------------------------

    def _t_send_email(
        self, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]:
        user = self._user_email()
        msg_id = f"msg_sent_{uuid4().hex[:8]}"
        thread_id = f"thread_sent_{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        thread = {
            "id": thread_id,
            "subject": subject,
            "participants": list({user, *to, *(cc or [])}),
            "labels": ["SENT"],
            "messages": [
                {
                    "id": msg_id,
                    "from": user,
                    "to": list(to),
                    "cc": list(cc or []),
                    "subject": subject,
                    "body": body,
                    "timestamp": now,
                }
            ],
            "unread": False,
            "kind_hint": "sent",
        }
        self.workspace.setdefault("gmail", {}).setdefault("threads", []).insert(0, thread)
        self._record("send_email", thread_id=thread_id, to=to, subject=subject)
        return {"ok": True, "thread_id": thread_id, "message_id": msg_id}

    def _t_reply_in_thread(self, thread_id: str, body: str) -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        msg_id = f"msg_sent_{uuid4().hex[:8]}"
        user = self._user_email()
        last = t["messages"][-1] if t.get("messages") else {}
        t.setdefault("messages", []).append(
            {
                "id": msg_id,
                "from": user,
                "to": [last.get("from")] if last.get("from") else [],
                "cc": [],
                "subject": f"Re: {t.get('subject', '')}",
                "body": body,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        t["unread"] = False
        self._record("reply_in_thread", thread_id=thread_id, message_id=msg_id)
        return {"ok": True, "thread_id": thread_id, "message_id": msg_id}

    def _t_forward_email(self, thread_id: str, to: list[str], note: str = "") -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        user = self._user_email()
        new_id = f"thread_fwd_{uuid4().hex[:8]}"
        original_body = t["messages"][-1].get("body", "") if t.get("messages") else ""
        now = datetime.now(timezone.utc).isoformat()
        fwd = {
            "id": new_id,
            "subject": f"Fwd: {t.get('subject', '')}",
            "participants": [user, *to],
            "labels": ["SENT", "FORWARDED"],
            "messages": [
                {
                    "id": f"msg_fwd_{uuid4().hex[:8]}",
                    "from": user,
                    "to": list(to),
                    "cc": [],
                    "subject": f"Fwd: {t.get('subject', '')}",
                    "body": (note + "\n\n---\n" if note else "") + original_body,
                    "timestamp": now,
                }
            ],
            "unread": False,
            "kind_hint": "forwarded",
        }
        self.workspace.setdefault("gmail", {}).setdefault("threads", []).insert(0, fwd)
        self._record("forward_email", original=thread_id, new_thread=new_id, to=to)
        return {"ok": True, "thread_id": new_id}

    def _t_archive_email(self, thread_id: str) -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        labels = t.setdefault("labels", [])
        if "ARCHIVED" not in labels:
            labels.append("ARCHIVED")
        self._record("archive_email", thread_id=thread_id)
        return {"ok": True}

    def _t_star_email(self, thread_id: str) -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        labels = t.setdefault("labels", [])
        if "STARRED" not in labels:
            labels.append("STARRED")
        self._record("star_email", thread_id=thread_id)
        return {"ok": True}

    def _t_add_label(self, thread_id: str, label: str) -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        labels = t.setdefault("labels", [])
        if label and label not in labels:
            labels.append(label)
        self._record("add_label", thread_id=thread_id, label=label)
        return {"ok": True}

    def _t_mark_read(self, thread_id: str) -> dict[str, Any]:
        t = self._find_thread(thread_id)
        if not t:
            return {"error": f"thread not found: {thread_id}"}
        t["unread"] = False
        self._record("mark_read", thread_id=thread_id)
        return {"ok": True}

    def _t_create_calendar_event(
        self, title: str, start_iso: str, end_iso: str, attendees: list[str]
    ) -> dict[str, Any]:
        user = self._user_email()
        new_id = f"evt_sim_{uuid4().hex[:8]}"
        ev = {
            "id": new_id,
            "title": title,
            "start": start_iso,
            "end": end_iso,
            "attendees": list({user, *attendees}),
            "organizer": user,
            "recurring": False,
            "location": "Zoom",
            "description": "Created via agent action.",
            "accepted": True,
        }
        self.workspace.setdefault("calendar", {}).setdefault("events", []).append(ev)
        self._record("create_calendar_event", event_id=new_id, title=title)
        return {"ok": True, "event_id": new_id}

    def _t_reschedule_event(
        self, event_id: str, new_start_iso: str, new_end_iso: str
    ) -> dict[str, Any]:
        ev = self._find_event(event_id)
        if not ev:
            return {"error": f"event not found: {event_id}"}
        old = {"start": ev.get("start"), "end": ev.get("end")}
        ev["start"] = new_start_iso
        ev["end"] = new_end_iso
        self._record(
            "reschedule_event",
            event_id=event_id,
            old=old,
            new={"start": new_start_iso, "end": new_end_iso},
        )
        return {"ok": True, "event_id": event_id}

    def _t_schedule_meeting_with_attendees(
        self,
        attendees: list[str],
        duration_minutes: int,
        from_iso: str,
        to_iso: str,
        title: str,
    ) -> dict[str, Any]:
        slot_result = self._t_find_free_slots(from_iso, to_iso, duration_minutes)
        if "error" in slot_result:
            return slot_result
        slots = slot_result.get("slots", [])
        if not slots:
            return {"error": "no free slot found in window", "slots": []}
        chosen = slots[0]
        try:
            start = datetime.fromisoformat(chosen["start"])
        except ValueError as e:
            return {"error": f"bad slot timestamp: {e}"}
        end = start + timedelta(minutes=duration_minutes)
        res = self._t_create_calendar_event(
            title=title,
            start_iso=start.isoformat(),
            end_iso=end.isoformat(),
            attendees=attendees,
        )
        if "error" in res:
            return res
        res["chosen_slot"] = {"start": start.isoformat(), "end": end.isoformat()}
        return res

    def _t_send_slack_message(self, channel: str, body: str) -> dict[str, Any]:
        target = None
        for ch in self.workspace.get("slack", {}).get("channels", []):
            if ch.get("name") == channel:
                target = ch
                break
        if target is None:
            return {"error": f"channel not found: {channel}"}
        msg_id = f"msg_sim_{uuid4().hex[:8]}"
        user = self.workspace.get("meta", {}).get("user", "me")
        target.setdefault("messages", []).append(
            {
                "id": msg_id,
                "user": self.workspace.get("slack", {}).get("user", "user_000"),
                "user_name": user,
                "text": body,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reactions": [],
                "thread_replies": [],
            }
        )
        self._record("send_slack_message", channel=channel, message_id=msg_id)
        return {"ok": True, "message_id": msg_id}

    def _t_send_dm(self, to: str, body: str) -> dict[str, Any]:
        dms = self.workspace.setdefault("slack", {}).setdefault("dms", [])
        target = None
        persona = self._find_persona(to)
        if persona:
            for dm in dms:
                if dm.get("with") == persona.get("id"):
                    target = dm
                    break
            if target is None:
                target = {
                    "id": f"D_sim_{uuid4().hex[:8]}",
                    "with": persona.get("id"),
                    "with_name": persona.get("name"),
                    "messages": [],
                    "unread": False,
                }
                dms.append(target)
        else:
            target = {
                "id": f"D_sim_{uuid4().hex[:8]}",
                "with": to,
                "with_name": to,
                "messages": [],
                "unread": False,
            }
            dms.append(target)
        msg_id = f"msg_sim_{uuid4().hex[:8]}"
        user_name = self.workspace.get("meta", {}).get("user", "me")
        target["messages"].append(
            {
                "id": msg_id,
                "user": self.workspace.get("slack", {}).get("user", "user_000"),
                "user_name": user_name,
                "text": body,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._record("send_dm", to=to, message_id=msg_id)
        return {"ok": True, "message_id": msg_id}

    def _t_react_slack(self, message_id: str, emoji: str) -> dict[str, Any]:
        for ch in self.workspace.get("slack", {}).get("channels", []):
            for m in ch.get("messages", []):
                if m.get("id") == message_id:
                    reactions = m.setdefault("reactions", [])
                    for r in reactions:
                        if r.get("emoji") == emoji:
                            r["count"] = r.get("count", 0) + 1
                            self._record("react_slack", message_id=message_id, emoji=emoji)
                            return {"ok": True}
                    reactions.append({"emoji": emoji, "count": 1})
                    self._record("react_slack", message_id=message_id, emoji=emoji)
                    return {"ok": True}
        return {"error": f"message not found: {message_id}"}

    def _t_share_file(self, file_id: str, **kwargs: Any) -> dict[str, Any]:
        # `with` is a Python keyword, so we accept it via **kwargs.
        with_who = kwargs.get("with")
        if with_who is None:
            return {"error": "missing 'with' argument"}
        f = self._find_file(file_id)
        if not f:
            return {"error": f"file not found: {file_id}"}
        persona = self._find_persona(with_who)
        email = persona.get("email") if persona else with_who
        shared = f.setdefault("shared_with", [])
        if email and email not in shared:
            shared.append(email)
        self._record("share_file", file_id=file_id, with_=email)
        return {"ok": True}

    def _t_comment_on_file(self, file_id: str, body: str, anchor: str = "§1") -> dict[str, Any]:
        f = self._find_file(file_id)
        if not f:
            return {"error": f"file not found: {file_id}"}
        comments_list = self.workspace.setdefault("drive", {}).setdefault("comments", [])
        cm_id = f"cm_sim_{uuid4().hex[:8]}"
        comments_list.append(
            {
                "id": cm_id,
                "thread_id": f"cth_sim_{uuid4().hex[:8]}",
                "file_id": file_id,
                "author": self._user_email(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "anchor": anchor,
                "body": body,
                "resolved": False,
                "is_reply": False,
            }
        )
        f["comment_count"] = f.get("comment_count", 0) + 1
        f["unresolved_comment_count"] = f.get("unresolved_comment_count", 0) + 1
        f["comments"] = f.get("comments", 0) + 1
        self._record("comment_on_file", file_id=file_id, comment_id=cm_id)
        return {"ok": True, "comment_id": cm_id}

    def _t_set_out_of_office(self, from_iso: str, to_iso: str, message: str) -> dict[str, Any]:
        meta = self.workspace.setdefault("meta", {})
        meta["out_of_office"] = {
            "from": from_iso,
            "to": to_iso,
            "message": message,
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        self._record("set_out_of_office", from_iso=from_iso, to_iso=to_iso)
        return {"ok": True}


# ---------------------------------------------------------------------------
# Agent protocol + built-in agents
# ---------------------------------------------------------------------------


class Agent(Protocol):
    name: str

    def act(self, observation: dict[str, Any]) -> AgentAction: ...


class MockAgent:
    """Deterministic agent for testing.

    Follows a fixed script that probes the main tools. Useful to exercise
    the harness end-to-end without any LLM dependency.
    """

    def __init__(
        self, name: str = "mock", final_answer: str = "Reviewed inbox and drafted replies."
    ) -> None:
        self.name = name
        self._final = final_answer
        self._step = 0

    def act(self, observation: dict[str, Any]) -> AgentAction:
        script = [
            AgentAction(
                thought="Scan inbox for important unread threads.",
                tool_calls=[
                    {
                        "name": "list_emails",
                        "arguments": {"label": "IMPORTANT", "unread_only": True, "limit": 5},
                    }
                ],
            ),
            AgentAction(
                thought="Read the top-ranked thread if any.",
                tool_calls=[{"name": "list_emails", "arguments": {"limit": 3}}],
            ),
            AgentAction(
                thought="Check calendar for conflicts today.",
                tool_calls=[{"name": "list_calendar", "arguments": {"limit": 10}}],
            ),
            AgentAction(
                thought="Check Slack mentions.",
                tool_calls=[{"name": "list_slack_mentions", "arguments": {}}],
            ),
            AgentAction(
                thought="Draft a response to the most urgent item.",
                tool_calls=[
                    {
                        "name": "draft_message",
                        "arguments": {
                            "to": "stakeholder",
                            "channel": "email",
                            "body": "Confirming — proceed with the plan. Will follow up by EOD.",
                        },
                    }
                ],
            ),
            AgentAction(
                thought="Done.",
                tool_calls=[],
                final_answer=self._final,
            ),
        ]
        if self._step >= len(script):
            return AgentAction(final_answer=self._final)
        action = script[self._step]
        self._step += 1
        return action


class OpenAIAgent:
    """OpenAI chat-completions adapter. Lazy-imports the SDK."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.2,
        name: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise click.ClickException(
                "openai package not installed. Install with: pip install 'inboxr[llm]'  "
                "(or: pip install openai)"
            ) from e
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        self.temperature = temperature
        self.name = name or f"openai:{model}"
        self._messages: list[dict[str, Any]] = []

    def act(self, observation: dict[str, Any]) -> AgentAction:
        if not self._messages:
            self._messages.append({"role": "system", "content": _system_prompt()})
            self._messages.append({"role": "user", "content": _format_observation(observation)})
        else:
            self._messages.append(
                {
                    "role": "user",
                    "content": "Tool results:\n"
                    + json.dumps(observation.get("tool_results", []), indent=2),
                }
            )

        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=self._messages,
        )
        content = resp.choices[0].message.content or ""
        self._messages.append({"role": "assistant", "content": content})
        return _parse_action(content)


class AnthropicAgent:
    """Anthropic messages-API adapter. Lazy-imports the SDK."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        max_tokens: int = 2048,
        name: str | None = None,
    ) -> None:
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise click.ClickException(
                "anthropic package not installed. Install with: pip install 'inboxr[llm]'  "
                "(or: pip install anthropic)"
            ) from e
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self.max_tokens = max_tokens
        self.name = name or f"anthropic:{model}"
        self._system = _system_prompt()
        self._messages: list[dict[str, Any]] = []

    def act(self, observation: dict[str, Any]) -> AgentAction:
        if not self._messages:
            self._messages.append({"role": "user", "content": _format_observation(observation)})
        else:
            self._messages.append(
                {
                    "role": "user",
                    "content": "Tool results:\n"
                    + json.dumps(observation.get("tool_results", []), indent=2),
                }
            )
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system,
            messages=self._messages,
        )
        content = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        self._messages.append({"role": "assistant", "content": content})
        return _parse_action(content)


def build_agent(spec: str) -> Agent:
    """Parse 'mock', 'openai:gpt-4o', 'anthropic:claude-sonnet-4-6' into an agent."""
    if spec == "mock":
        return MockAgent()
    if ":" not in spec:
        raise ValueError(f"agent spec must be 'mock' or '<provider>:<model>', got {spec!r}")
    provider, model = spec.split(":", 1)
    if provider == "openai":
        return OpenAIAgent(model=model)
    if provider == "anthropic":
        return AnthropicAgent(model=model)
    raise ValueError(f"unknown agent provider: {provider}")


# ---------------------------------------------------------------------------
# Prompting helpers (shared by OpenAI/Anthropic adapters)
# ---------------------------------------------------------------------------


def _system_prompt() -> str:
    tools_json = json.dumps(WorkspaceTools.SPEC, indent=2)
    return (
        "You are an AI assistant helping the user manage their digital workspace.\n"
        "You have access to the following tools. Respond ONLY with a JSON object\n"
        "of the form:\n"
        '{"thought": "...", "tool_calls": [{"name": "...", "arguments": {...}}], "final_answer": null}\n'
        "When you are done, set final_answer to a short summary and tool_calls to [].\n\n"
        f"Tools:\n{tools_json}\n"
    )


# Maximum number of inbox rows sent to the model on the first observation.
# Keeping this small avoids context-window overflows on crisis-difficulty
# workspaces (200+ threads).  The agent can always call list_emails / search_emails
# to fetch more.
_INBOX_PREVIEW_LIMIT = 15
_CALENDAR_PREVIEW_LIMIT = 10
_MENTIONS_PREVIEW_LIMIT = 10
_SLACK_CHANNELS_PREVIEW_LIMIT = 8


def _format_observation(obs: dict[str, Any]) -> str:
    parts = [f"Task: {obs.get('task', '')}"]

    workspace = obs.get("workspace") or {}
    if workspace:
        # Emails — compact list, no bodies. Agent uses read_email for full content.
        threads = workspace.get("gmail", {}).get("threads", [])
        unread = [t for t in threads if t.get("unread")]
        important = [t for t in threads if "IMPORTANT" in t.get("labels", [])]
        # Show unread/important first, then fill up to the limit
        preview_set: list[dict[str, Any]] = []
        seen: set[str] = set()
        for t in unread + important + threads:
            if t.get("id") not in seen:
                preview_set.append(t)
                seen.add(t.get("id", ""))
            if len(preview_set) >= _INBOX_PREVIEW_LIMIT:
                break

        if preview_set:
            email_list = []
            for t in preview_set:
                first_msg = (t.get("messages") or [{}])[0]
                email_list.append(
                    {
                        "id": t.get("id"),
                        "subject": t.get("subject"),
                        "from": first_msg.get("from"),
                        "unread": t.get("unread"),
                        "labels": t.get("labels", []),
                        "timestamp": first_msg.get("timestamp"),
                    }
                )
            total = len(threads)
            parts.append(
                f"Inbox ({total} total threads — showing {len(email_list)} most relevant).\n"
                "Use list_emails or search_emails to find more. Use read_email to get the full body.\n"
                + json.dumps(email_list, indent=2)
            )

        # Calendar — compact, conflicts first
        cal = workspace.get("calendar", {})
        conflict_ids = {c["event_a"] for c in cal.get("conflicts", [])} | {
            c["event_b"] for c in cal.get("conflicts", [])
        }
        events = sorted(
            cal.get("events", []),
            key=lambda e: (0 if e.get("id") in conflict_ids else 1, e.get("start", "")),
        )[:_CALENDAR_PREVIEW_LIMIT]
        if events:
            parts.append(
                "Calendar (conflicts shown first):\n"
                + json.dumps(
                    [
                        {
                            "id": e.get("id"),
                            "title": e.get("title"),
                            "start": e.get("start"),
                            "end": e.get("end"),
                            "conflict": e.get("id") in conflict_ids,
                        }
                        for e in events
                    ],
                    indent=2,
                )
            )

        # Slack — show channel list + unread mentions so the agent knows where to act
        slack = workspace.get("slack", {})
        mentions = slack.get("mentions", [])
        if mentions:
            parts.append(
                "Slack mentions (most recent):\n"
                + json.dumps(mentions[:_MENTIONS_PREVIEW_LIMIT], indent=2)
            )

        # Always surface the channel list so the agent picks the right channel
        # even when there are no @-mentions (e.g. crisis scenarios).
        channels = slack.get("channels", [])
        if channels:
            chan_preview = [
                {
                    "name": ch.get("name"),
                    "topic": ch.get("topic"),
                    "unread_count": ch.get("unread_count", 0),
                }
                for ch in channels[:_SLACK_CHANNELS_PREVIEW_LIMIT]
            ]
            parts.append(
                "Slack channels (use send_slack_message / read_slack_channel to interact):\n"
                + json.dumps(chan_preview, indent=2)
            )
    else:
        summary = obs.get("workspace_summary") or {}
        if summary:
            parts.append("Workspace summary: " + json.dumps(summary))

    return "\n".join(parts)


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    """Extract all top-level JSON objects from a string using brace counting.

    Claude sometimes emits multiple JSON objects in a single response — one per
    reasoning step.  A simple greedy regex grabs everything between the first {
    and the last }, which mangles nested structures.  This function walks the
    string character-by-character and correctly splits on balanced braces.
    """
    objects: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = -1
    return objects


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)  # kept for legacy callers


def _parse_action(text: str) -> AgentAction:
    """Extract the *first actionable* JSON object from a model response.

    Claude sometimes emits several JSON objects in one turn (one per reasoning
    step).  We scan all of them and pick the first one that either has
    non-empty ``tool_calls`` or a non-null ``final_answer``.  If none qualifies
    we fall back to the first parseable object, and if nothing parses we treat
    the whole text as a terminal final answer.
    """
    raw = text or ""
    candidates = _extract_json_objects(raw)

    if not candidates:
        return AgentAction(thought=raw, final_answer=raw.strip() or "[no content]")

    # Priority 1: has non-empty tool_calls → agent wants to act.
    for data in candidates:
        if data.get("tool_calls"):
            return AgentAction(
                thought=data.get("thought", "") or "",
                tool_calls=data.get("tool_calls", []),
                final_answer=data.get("final_answer"),
            )

    # Priority 2: has an explicit final_answer → agent is done.
    for data in candidates:
        if data.get("final_answer") is not None:
            return AgentAction(
                thought=data.get("thought", "") or "",
                tool_calls=[],
                final_answer=data.get("final_answer"),
            )

    # Fallback: first parseable object.
    data = candidates[0]
    return AgentAction(
        thought=data.get("thought", "") or "",
        tool_calls=data.get("tool_calls", []) or [],
        final_answer=data.get("final_answer"),
    )


# ---------------------------------------------------------------------------
# Rubric scoring
# ---------------------------------------------------------------------------


class Rubric:
    """Scores a trajectory against the scenario's success_criteria.

    Two modes:
      * heuristic (default) — keyword-based over tool_calls + drafts
      * llm-judge           — calls an Anthropic/OpenAI model, returns pass/fail + reason

    The heuristic is coarse but deterministic — good for CI and for testing
    the pipeline without burning API credits.
    """

    def __init__(self, judge: str = "heuristic") -> None:
        self.judge = judge

    def score(
        self,
        scenario: dict[str, Any],
        trajectory: list[TrajectoryStep],
        drafts: list[dict[str, Any]],
        final_answer: str,
    ) -> list[dict[str, Any]]:
        if self.judge == "heuristic":
            return self._score_heuristic(scenario, trajectory, drafts, final_answer)
        if self.judge.startswith("anthropic") or self.judge.startswith("openai"):
            return self._score_llm(scenario, trajectory, drafts, final_answer)
        raise ValueError(f"unknown judge: {self.judge}")

    # --- heuristic ---------------------------------------------------------

    def _score_heuristic(
        self,
        scenario: dict[str, Any],
        trajectory: list[TrajectoryStep],
        drafts: list[dict[str, Any]],
        final_answer: str,
    ) -> list[dict[str, Any]]:
        tools_used = {tc["name"] for step in trajectory for tc in step.tool_calls}
        all_text = " ".join(
            [step.thought or "" for step in trajectory]
            + [json.dumps(tc.get("arguments", {})) for step in trajectory for tc in step.tool_calls]
            + [d.get("body", "") for d in drafts]
            + [final_answer or ""]
        ).lower()

        out = []
        for criterion in scenario.get("success_criteria", []):
            passed, reason = self._criterion_heuristic(criterion, tools_used, drafts, all_text)
            out.append({"criterion": criterion, "passed": passed, "justification": reason})
        return out

    @staticmethod
    def _criterion_heuristic(criterion: str, tools_used: set, drafts: list, all_text: str):
        c = criterion.lower()

        # Did the agent explore inbox?
        if "email" in c and "identifies" in c:
            ok = "list_emails" in tools_used or "read_email" in tools_used
            return ok, "Agent queried the inbox." if ok else "Agent never read email."

        # Incident / crisis response — matched BEFORE the generic draft heuristic
        # because "response" appears in many crisis criteria but drafts aren't
        # the only valid action (send_slack_message, send_dm, reply_in_thread
        # are all valid incident-response actions).
        if "incident" in c or "crisis" in c or "prioriti" in c or "optic" in c:
            action_tools = {
                "draft_email_reply",
                "draft_message",
                "send_email",
                "reply_in_thread",
                "forward_email",
                "send_slack_message",
                "send_dm",
                "read_slack_channel",
                "search_slack",
                "list_slack_channels",
            }
            incident_words = (
                "incident",
                "rollback",
                "forward-fix",
                "engineer",
                "ceo",
                "customer",
                "status page",
                "channel",
                "coordinate",
                "triage",
                "production",
            )
            ok = (
                len(drafts) > 0
                or bool(tools_used & action_tools)
                or any(w in all_text for w in incident_words)
            )
            return (
                ok,
                "Agent took incident-response actions."
                if ok
                else "No incident response content detected.",
            )

        # Did the agent draft something when a draft was required?
        if (
            "draft" in c
            or "apolog" in c
            or "reschedule" in c
            or ("response" in c and "incident" not in c)
        ):
            ok = len(drafts) > 0
            return ok, f"{len(drafts)} draft(s) produced." if ok else "No drafts produced."

        # Calendar-aware criteria
        if "calendar" in c or "schedul" in c or "meeting" in c or "conflict" in c:
            ok = "list_calendar" in tools_used
            return (
                ok,
                "Agent inspected the calendar." if ok else "Agent never looked at the calendar.",
            )

        # Slack / channel awareness — check both reading and writing Slack
        if "slack" in c or "channel" in c or "mention" in c or "dm" in c:
            slack_tools = {
                "list_slack_mentions",
                "list_slack_channels",
                "read_slack_channel",
                "search_slack",
                "send_slack_message",
                "send_dm",
                "list_dms",
                "read_dm",
            }
            ok = bool(tools_used & slack_tools)
            return ok, "Agent used Slack." if ok else "Agent ignored Slack."

        # Drive / onboarding / document discovery
        if "onboard" in c or "doc" in c or "drive" in c or "locat" in c:
            ok = "search_drive" in tools_used
            return ok, "Agent searched Drive." if ok else "Agent did not search Drive."

        # Deferral / triage — at least some signal the agent summarized instead of spamming drafts
        if "defer" in c or "triage" in c or "summarize" in c:
            ok = bool(all_text) and (
                "summar" in all_text or "defer" in all_text or len(drafts) <= 3
            )
            return ok, "Agent deferred low-priority items." if ok else "Agent did not triage."

        # Stakeholder / tone / relationship awareness — fuzzy
        if "stakeholder" in c or "tone" in c or "relationship" in c:
            ok = any(word in all_text for word in ("stakeholder", "tone", "team", "manager"))
            return (
                ok,
                "Agent referenced stakeholders." if ok else "No stakeholder reasoning detected.",
            )

        # Timeline / over-commit / pressure — agent avoids promising specific ETAs without hedging.
        # We PASS when either (a) the agent used hedging language, or (b) the agent
        # produced no outbound comms at all (drafts/sends) — since you can't
        # over-commit a timeline if you haven't committed to anything yet.
        if "timeline" in c or "over-commit" in c or "commit" in c or "pressure" in c:
            hedge_words = (
                "investigating",
                "working on",
                "no eta",
                "tbd",
                "unknown",
                "will update",
                "keep you posted",
                "as soon as",
                "once we know",
                "pending",
                "assess",
                "unclear",
                "cannot confirm",
                "coordinate",
                "plan",
                "priorit",
                "gather",
                "triage",
                "looking into",
                "update you",
                "more info",
                "monitoring",
                "ongoing",
            )
            send_tools = {
                "send_email",
                "reply_in_thread",
                "forward_email",
                "send_slack_message",
                "send_dm",
            }
            committed = bool(drafts) or bool(tools_used & send_tools)
            used_hedge = any(w in all_text for w in hedge_words)
            # You can't over-commit a timeline if you haven't committed anything yet.
            ok = used_hedge or not committed
            if used_hedge:
                reason = "Agent used hedged language — no hard timeline over-committed."
            elif not committed:
                reason = "Agent sent no outbound comms yet — no timeline committed."
            else:
                reason = "Agent may have over-committed a timeline (no hedging detected)."
            return ok, reason

        # Fallback — criterion unmatched by heuristics; mark as inconclusive (pass=False, clear reason)
        return False, "No heuristic for this criterion; use --judge llm for a real score."

    # --- llm judge ---------------------------------------------------------

    def _score_llm(
        self,
        scenario: dict[str, Any],
        trajectory: list[TrajectoryStep],
        drafts: list[dict[str, Any]],
        final_answer: str,
    ) -> list[dict[str, Any]]:
        provider, _, model = self.judge.partition(":")
        model = model or ("claude-sonnet-4-6" if provider == "anthropic" else "gpt-4o-mini")

        prompt = (
            "You are grading an AI agent's handling of a workspace task.\n"
            f"Task:\n{scenario.get('task', '')}\n\n"
            "Success criteria:\n"
            + "\n".join(f"- {c}" for c in scenario.get("success_criteria", []))
            + "\n\nTrajectory (thoughts + tool calls):\n"
            + json.dumps([asdict(s) for s in trajectory], indent=2)[:12000]
            + f"\n\nDrafts: {json.dumps(drafts, indent=2)[:4000]}"
            + f"\n\nAgent's final answer: {final_answer}\n\n"
            "For each criterion return a JSON array of "
            '{"criterion": str, "passed": bool, "justification": str}. '
            "Respond with JSON only."
        )

        if provider == "anthropic":
            try:
                import anthropic  # type: ignore
            except ImportError as e:
                raise click.ClickException(
                    "anthropic package not installed. Install with: pip install 'inboxr[llm]'"
                ) from e
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        elif provider == "openai":
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as e:
                raise click.ClickException(
                    "openai package not installed. Install with: pip install 'inboxr[llm]'"
                ) from e
            client = OpenAI()
            resp = client.chat.completions.create(
                model=model,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.choices[0].message.content or ""
        else:
            raise ValueError(f"unknown judge provider: {provider}")

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return [
                {"criterion": c, "passed": False, "justification": "judge returned no JSON"}
                for c in scenario.get("success_criteria", [])
            ]
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return [
                {"criterion": c, "passed": False, "justification": "judge JSON malformed"}
                for c in scenario.get("success_criteria", [])
            ]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_eval(
    scenario: dict[str, Any],
    agent: Agent,
    rubric: Rubric | None = None,
    max_steps: int = 10,
) -> EvalResult:
    """Run one agent against one scenario and score it."""
    rubric = rubric or Rubric()
    tools = WorkspaceTools(scenario["workspace"])

    workspace_summary = {
        "emails": scenario["workspace"].get("gmail", {}).get("summary", {}),
        "calendar": scenario["workspace"].get("calendar", {}).get("summary", {}),
        "slack": scenario["workspace"].get("slack", {}).get("summary", {}),
        "drive": scenario["workspace"].get("drive", {}).get("summary", {}),
    }
    # Pass a *compact* workspace preview on the first observation so we don't
    # flood the model's context window on high-difficulty scenarios (200+ emails).
    # _format_observation trims threads/events/mentions to a small fixed limit;
    # the agent uses tool calls to fetch the rest.
    observation: dict[str, Any] = {
        "task": scenario.get("task", ""),
        "workspace_summary": workspace_summary,
        "workspace": scenario.get("workspace", {}),
        "tool_results": [],
    }

    trajectory: list[TrajectoryStep] = []
    final_answer = ""
    stopped_reason = "max_steps"
    started = datetime.now(timezone.utc).isoformat()

    for step in range(max_steps):
        try:
            action = agent.act(observation)
        except Exception as e:  # noqa: BLE001
            trajectory.append(TrajectoryStep(step, f"agent error: {e}", [], []))
            stopped_reason = "error"
            break

        tool_results = [tools.apply(tc) for tc in action.tool_calls]
        trajectory.append(
            TrajectoryStep(
                step=step,
                thought=action.thought,
                tool_calls=action.tool_calls,
                tool_results=tool_results,
                final_answer=action.final_answer,
            )
        )

        if action.is_terminal():
            final_answer = action.final_answer or ""
            stopped_reason = "terminal"
            break

        observation = {
            "task": scenario.get("task", ""),
            "tool_results": tool_results,
        }

    criteria_scores = rubric.score(scenario, trajectory, tools.drafts, final_answer)
    passed = sum(1 for c in criteria_scores if c["passed"])
    total = max(1, len(criteria_scores))

    return EvalResult(
        scenario_id=scenario.get("id", ""),
        template=scenario.get("template", ""),
        agent_name=getattr(agent, "name", "unknown"),
        trajectory=trajectory,
        criteria_scores=criteria_scores,
        score=passed / total,
        final_answer=final_answer,
        stopped_reason=stopped_reason,
        started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
