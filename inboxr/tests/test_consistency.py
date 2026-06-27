"""Tests for the consistency engine."""

import copy

from inboxr import (
    build_reference_graph,
    check_consistency,
    generate_workspace,
    repair_consistency,
)


def test_fresh_workspace_has_no_integrity_errors():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    report = check_consistency(ws)
    # A freshly generated workspace should never have reference-integrity
    # errors (orphan emails, missing parent folders, etc). Warnings/info are
    # allowed — they describe weak scenario signals, not broken data.
    assert report.error_count == 0, [
        (v.code, v.message) for v in report.violations if v.severity == "error"
    ]


def test_orphan_email_sender_is_caught():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    ws["gmail"]["threads"][0]["messages"][0]["from"] = "ghost@nowhere.com"
    report = check_consistency(ws)
    codes = {v.code for v in report.violations}
    assert "orphan_email_sender" in codes


def test_orphan_event_attendee_is_caught():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    ws["calendar"]["events"][0]["attendees"].append("stranger@example.com")
    report = check_consistency(ws)
    codes = {v.code for v in report.violations}
    assert "orphan_event_attendee" in codes


def test_repair_removes_orphan_attendees():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    ws["calendar"]["events"][0]["attendees"].append("stranger@example.com")
    _, report = repair_consistency(ws)
    attendees = ws["calendar"]["events"][0]["attendees"]
    assert "stranger@example.com" not in attendees
    assert any(r.code == "orphan_event_attendee" for r in report.repaired) or not any(
        v.code == "orphan_event_attendee" for v in report.violations
    )


def test_repair_fixes_orphan_file_owner():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    ws["drive"]["files"][0]["owner"] = "ghost@nowhere.com"
    _, report = repair_consistency(ws)
    assert ws["drive"]["files"][0]["owner"] != "ghost@nowhere.com"
    assert any(r.code == "orphan_file_owner" for r in report.repaired)


def test_reply_before_original_detected():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=6)
    # Find a thread with multiple messages and invert order
    for thread in ws["gmail"]["threads"]:
        if len(thread["messages"]) >= 2:
            thread["messages"][0]["timestamp"] = "2026-04-20T12:00:00"
            thread["messages"][1]["timestamp"] = "2026-04-20T09:00:00"
            break
    else:
        # No multi-message thread in this fixture; skip softly
        return
    report = check_consistency(ws)
    assert any(v.code == "reply_before_original" for v in report.violations)


def test_event_end_before_start_detected():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    ev = ws["calendar"]["events"][0]
    ev["start"] = "2026-04-20T10:00:00"
    ev["end"] = "2026-04-20T09:00:00"
    report = check_consistency(ws)
    assert any(v.code == "event_end_before_start" for v in report.violations)


def test_report_is_serializable():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    report = check_consistency(ws)
    d = report.to_dict()
    assert "violations" in d
    assert "is_consistent" in d


def test_repair_is_idempotent():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    ws["drive"]["files"][0]["owner"] = "ghost@nowhere.com"
    repair_consistency(ws)
    snapshot = copy.deepcopy(ws)
    repair_consistency(ws)
    assert ws == snapshot


# ---------------------------------------------------------------------------
# Graph-based checks
# ---------------------------------------------------------------------------


def test_build_reference_graph_has_personas_and_projects():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=6)
    graph = build_reference_graph(ws)
    persona_nodes = graph.nodes_of_type("persona")
    project_nodes = graph.nodes_of_type("project")
    # Every persona must be a node.
    assert len(persona_nodes) == len(ws["personas"])
    # Projects are always present in medium difficulty generators.
    assert len(project_nodes) >= 1


def test_reference_graph_marks_systems_for_project():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=6)
    graph = build_reference_graph(ws)
    # At least one project node ought to be grounded in drive or calendar.
    grounded = [
        node
        for node in graph.nodes_of_type("project")
        if graph.systems_for(node) & {"drive", "calendar"}
    ]
    assert grounded, "no project node was grounded in drive or calendar"


def test_repair_grounds_project_without_artifact():
    """A project mentioned only in Gmail should get a stub Drive file."""
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)

    # Inject a ghost project into a Gmail subject + body. "churn analysis"
    # is in the known PROJECT_PATTERN so it registers on the graph.
    thread = ws["gmail"]["threads"][0]
    thread["subject"] = "Re: churn analysis pushback"
    thread["messages"][0]["body"] = "Need input on churn analysis before Friday."

    # Remove any drive files / calendar events that already cover it so the
    # un-grounded state is guaranteed even if the generator happened to plant
    # something relevant.
    ws["drive"]["files"] = [
        f for f in ws["drive"]["files"] if "churn" not in f.get("name", "").lower()
    ]
    ws["calendar"]["events"] = [
        e for e in ws["calendar"]["events"] if "churn" not in e.get("title", "").lower()
    ]

    pre = check_consistency(ws)
    assert any(
        v.code == "project_without_artifact" and v.ref.get("project") == "churn analysis"
        for v in pre.violations
    )

    _, report = repair_consistency(ws)
    # The repair must have created a stub Drive file for the uncovered project.
    assert any(
        r.code == "project_without_artifact" and r.ref.get("project") == "churn analysis"
        for r in report.repaired
    )
    assert any(
        f.get("synthesised_by_repair") and "churn" in f.get("name", "").lower()
        for f in ws["drive"]["files"]
    )
    # And the post-repair report should no longer list that project as
    # un-grounded.
    assert not any(
        v.code == "project_without_artifact" and v.ref.get("project") == "churn analysis"
        for v in report.violations
    )


def test_repair_preserves_existing_drive_files():
    """Project coverage repair must never touch files that already exist."""
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=6)
    before = {f["id"]: dict(f) for f in ws["drive"]["files"]}
    repair_consistency(ws)
    for fid, before_file in before.items():
        match = next((f for f in ws["drive"]["files"] if f["id"] == fid), None)
        assert match is not None, f"repair lost existing file {fid}"
        # Core immutable fields stay the same.
        assert match["name"] == before_file["name"]
        assert match["owner"] == before_file["owner"]


def test_drive_version_before_created_detected():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    # Find a file with at least one version.
    for f in ws["drive"]["files"]:
        if f.get("versions"):
            f["created"] = "2026-04-01T00:00:00"
            f["versions"][0]["timestamp"] = "2025-01-01T00:00:00"
            break
    else:
        return  # no versioned files in this fixture
    report = check_consistency(ws)
    assert any(v.code == "version_before_file_created" for v in report.violations)


def test_whatsapp_reply_to_unknown_message_is_caught():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=6)
    # Find any chat and inject a bogus reply-to pointer on its first message.
    chats = ws.get("whatsapp", {}).get("chats", [])
    assert chats, "fixture lacks whatsapp chats"
    chats[0]["messages"][0]["reply_to"] = {
        "message_id": "wa_does_not_exist",
        "snippet": "...",
    }
    report = check_consistency(ws)
    assert any(v.code == "orphan_whatsapp_reply_target" for v in report.violations)


def test_repair_drops_dangling_whatsapp_reply_to():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=6)
    chats = ws.get("whatsapp", {}).get("chats", [])
    assert chats, "fixture lacks whatsapp chats"
    chats[0]["messages"][0]["reply_to"] = {
        "message_id": "wa_does_not_exist",
        "snippet": "...",
    }
    repair_consistency(ws)
    assert "reply_to" not in chats[0]["messages"][0]


def test_persona_never_referenced_is_info_only():
    """Orphan personas are flagged as info, never error."""
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    # Add a stranded persona that no system ever references.
    ws["personas"].append(
        {
            "id": "p_ghost",
            "name": "Ghost Persona",
            "email": "ghost@ghostcorp.example",
            "role": "Intern",
            "department": "design",
            "tone": "friendly",
            "working_hours": [9, 17],
            "timezone": "UTC",
            "relationships": {},
            "slack_handle": "@ghost",
            "phone": "+1-555-0000",
            "relationship_history": [],
            "trust_score": {},
        }
    )
    report = check_consistency(ws)
    ghost_hits = [v for v in report.violations if v.code == "persona_never_referenced"]
    assert any(v.ref.get("persona_id") == "p_ghost" for v in ghost_hits)
    assert all(v.severity == "info" for v in ghost_hits)
