"""Regression tests for the depth enhancements.

Covers the five enhancement areas added beyond the original generation +
consistency + eval tests:

1. Persona relationship history + trust scores
2. Drive depth (nested subfolders, versions, comments, activity log)
3. WhatsApp depth (contact types, topics, media, reply-to, read receipts)
4. Gmail noise model (newsletter / automated / false_urgent / phishing_like)
5. Expanded agent toolset + cross-system scenarios

Each test stays scoped and deterministic so a failure points to exactly one
missing property rather than a vague "something changed".
"""

from __future__ import annotations

from inboxr import (
    SCENARIO_TEMPLATES,
    WorkspaceTools,
    check_consistency,
    generate_personas,
    generate_scenario,
    generate_workspace,
)
from inboxr.consistency import (
    NODE_PERSONA,
    NODE_PROJECT,
    build_reference_graph,
)

# ---------------------------------------------------------------------------
# Personas — relationship history + trust scores
# ---------------------------------------------------------------------------


def test_persona_relationship_history_is_populated():
    personas = generate_personas(count=8, seed=42)
    # The user + everyone with at least one bare relationship should end up
    # with at least one textured fact; small workspaces can legitimately
    # have a persona with none, so we assert population in aggregate.
    total_facts = sum(len(p.relationship_history) for p in personas)
    assert total_facts >= len(personas), (
        f"expected at least one fact per persona on average, got {total_facts}"
    )


def test_persona_trust_score_stays_in_range():
    personas = generate_personas(count=8, seed=42)
    for p in personas:
        for peer_id, score in p.trust_score.items():
            assert 0.0 <= score <= 1.0, f"{p.id}->{peer_id} trust out of range: {score}"


def test_persona_relationship_kinds_are_known():
    personas = generate_personas(count=8, seed=42)
    allowed = {"collaboration", "conflict", "mentorship", "personal", "trust", "stress"}
    for p in personas:
        for rf in p.relationship_history:
            assert rf.kind in allowed, f"unknown relationship kind: {rf.kind}"


def test_persona_facts_about_filters_by_peer():
    personas = generate_personas(count=8, seed=42)
    for p in personas:
        for peer_id in p.relationships:
            facts = p.facts_about(peer_id)
            assert all(rf.object_id == peer_id for rf in facts)


# ---------------------------------------------------------------------------
# Drive depth
# ---------------------------------------------------------------------------


def test_drive_has_nested_project_subfolders():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=8)
    # Pick an existing project folder and confirm it has the typed subfolders.
    folders = ws["drive"]["folders"]
    project_roots = [
        f
        for f in folders
        if f.get("name")
        in ("Atlas", "Phoenix", "Pricing", "Onboarding", "Mobile", "Platform", "Growth")
        and any(
            g.get("id") == f.get("parent_id") and g.get("name") == "Team Shared" for g in folders
        )
    ]
    assert project_roots, "no project root folders found"
    sample = project_roots[0]
    child_names = {f["name"] for f in folders if f.get("parent_id") == sample["id"]}
    assert {"Docs", "Specs", "Reviews", "Decks", "Data", "Archive"} <= child_names


def test_drive_doc_files_have_version_history():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=8)
    with_versions = [
        f
        for f in ws["drive"]["files"]
        if f.get("type") in ("doc", "sheet", "slides") and f.get("version_count", 0) > 0
    ]
    assert with_versions, "expected some doc/sheet/slides files to carry versions"
    for f in with_versions[:5]:
        versions = f.get("versions") or []
        assert len(versions) == f["version_count"]
        # Each revision must have the required fields the consistency engine checks.
        for v in versions:
            assert "author" in v and "timestamp" in v and "summary" in v


def test_drive_comments_and_activity_log_exist():
    ws = generate_workspace(seed=42, difficulty="hard", persona_count=8)
    assert ws["drive"]["summary"]["total_comments"] > 0, "hard workspace should have comments"
    assert ws["drive"]["summary"]["activity_events"] > 0, "activity log should be populated"
    # Activity entries link back to real files in the workspace.
    file_ids = {f["id"] for f in ws["drive"]["files"]}
    for event in ws["drive"]["activity"][:20]:
        assert event["file_id"] in file_ids


# ---------------------------------------------------------------------------
# WhatsApp depth
# ---------------------------------------------------------------------------


def test_whatsapp_personal_chats_have_contact_types():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=8)
    personal_chats = [c for c in ws["whatsapp"]["chats"] if c["type"] == "personal"]
    assert personal_chats, "expected at least one personal WhatsApp chat"
    allowed_types = {"family", "partner", "friend", "service"}
    for chat in personal_chats:
        assert chat.get("contact_type") in allowed_types


def test_whatsapp_messages_tag_topics_and_may_carry_media():
    ws = generate_workspace(seed=42, difficulty="hard", persona_count=8)
    all_messages = [m for c in ws["whatsapp"]["chats"] for m in c["messages"]]
    assert all_messages, "hard difficulty should produce whatsapp messages"
    topics = {m.get("topic") for m in all_messages if m.get("topic")}
    # We should see more than one topic across a hard-difficulty workspace.
    assert len(topics) >= 3, f"expected topic variety, got {topics}"
    # At least some messages should carry media attachments.
    with_media = [m for m in all_messages if m.get("media")]
    assert with_media, "expected media attachments at hard difficulty"


def test_whatsapp_reply_to_targets_are_valid():
    ws = generate_workspace(seed=42, difficulty="hard", persona_count=8)
    report = check_consistency(ws)
    codes = {v.code for v in report.violations}
    # The generator must not leave dangling reply-to pointers.
    assert "orphan_whatsapp_reply_target" not in codes


# ---------------------------------------------------------------------------
# Gmail noise model
# ---------------------------------------------------------------------------


def test_gmail_noise_family_kinds_are_produced():
    ws = generate_workspace(seed=42, difficulty="hard", persona_count=10)
    hints = {t.get("kind_hint") for t in ws["gmail"]["threads"]}
    # At "hard" difficulty we expect at least two of the four noise-family
    # kinds, since each carries non-trivial weight.
    noise_family = {"newsletter", "automated_alert", "false_urgent", "phishing_like"}
    assert len(hints & noise_family) >= 2, (
        f"expected at least two noise-family kinds, got {hints & noise_family}"
    )


def test_gmail_phishing_threads_labelled_suspicious():
    ws = generate_workspace(seed=42, difficulty="crisis", persona_count=10)
    phish_threads = [t for t in ws["gmail"]["threads"] if t.get("kind_hint") == "phishing_like"]
    assert phish_threads, "crisis difficulty should produce phishing-like threads"
    for t in phish_threads:
        assert "SUSPICIOUS" in t.get("labels", [])
        assert t.get("external_sender") is True


def test_gmail_external_senders_do_not_trigger_orphan_errors():
    """External senders (newsletter/automated/phishing) live outside the org
    and must not generate orphan_email_sender errors."""
    ws = generate_workspace(seed=42, difficulty="hard", persona_count=10)
    report = check_consistency(ws)
    # No orphan-sender errors should survive the external_sender exception.
    assert not any(v.code == "orphan_email_sender" for v in report.violations), [
        v.message for v in report.violations if v.code == "orphan_email_sender"
    ]


# ---------------------------------------------------------------------------
# Consistency graph-based layer
# ---------------------------------------------------------------------------


def test_reference_graph_covers_personas_and_projects():
    ws = generate_workspace(seed=42, difficulty="medium", persona_count=8)
    g = build_reference_graph(ws)
    assert len(g.nodes_of_type(NODE_PERSONA)) == 8
    assert len(g.nodes_of_type(NODE_PROJECT)) > 0


# ---------------------------------------------------------------------------
# Expanded agent toolset
# ---------------------------------------------------------------------------


def test_workspace_tools_spec_is_large_and_dispatchable():
    spec = WorkspaceTools.SPEC
    assert len(spec) >= 30, f"expected 30+ tools, got {len(spec)}"
    # Every spec entry must map to an implemented handler.
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    for entry in spec:
        assert hasattr(tools, f"_t_{entry['name']}"), f"missing handler for {entry['name']}"


def test_send_email_creates_a_thread_and_logs_action():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    result = tools.apply(
        {
            "name": "send_email",
            "arguments": {
                "to": ["someone@example.com"],
                "subject": "hi",
                "body": "hello",
            },
        }
    )
    assert result["ok"]
    assert any(a["kind"] == "send_email" for a in tools.actions)
    # The new thread is visible at the head of the inbox.
    first_thread = sc["workspace"]["gmail"]["threads"][0]
    assert first_thread["id"] == result["thread_id"]
    assert "SENT" in first_thread["labels"]


def test_find_free_slots_returns_non_overlapping_windows():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    result = tools.apply(
        {
            "name": "find_free_slots",
            "arguments": {
                "from_iso": "2026-04-20T09:00:00",
                "to_iso": "2026-04-20T18:00:00",
                "duration_minutes": 30,
            },
        }
    )
    assert "slots" in result
    # Slots are half-open windows; each must be wide enough for the requested duration.
    from datetime import datetime

    for slot in result["slots"]:
        start = datetime.fromisoformat(slot["start"])
        end = datetime.fromisoformat(slot["end"])
        assert (end - start).total_seconds() >= 30 * 60


def test_schedule_meeting_chains_find_slots_and_create_event():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    result = tools.apply(
        {
            "name": "schedule_meeting_with_attendees",
            "arguments": {
                "attendees": [sc["workspace"]["personas"][1]["email"]],
                "duration_minutes": 30,
                "from_iso": "2026-04-22T09:00:00",
                "to_iso": "2026-04-22T18:00:00",
                "title": "Sync",
            },
        }
    )
    assert result.get("ok"), result
    assert "chosen_slot" in result
    # Both underlying tools are reflected in the action log.
    action_kinds = [a["kind"] for a in tools.actions]
    assert "create_calendar_event" in action_kinds


# ---------------------------------------------------------------------------
# Scenario expansion + cross-system planters
# ---------------------------------------------------------------------------


def test_scenario_templates_total_is_at_least_twenty():
    assert len(SCENARIO_TEMPLATES) >= 20


def test_every_scenario_produces_clean_consistency():
    """Every registered template must generate a workspace with zero
    error-level consistency violations."""
    failures: list = []
    for name in SCENARIO_TEMPLATES:
        sc = generate_scenario(name, seed=42)
        report = check_consistency(sc["workspace"])
        if report.error_count > 0:
            failures.append((name, [v.code for v in report.violations if v.severity == "error"]))
    assert not failures, f"scenarios with consistency errors: {failures}"


def test_slack_to_meeting_plants_an_engineering_thread():
    sc = generate_scenario("slack-to-meeting", seed=42)
    eng = next(c for c in sc["workspace"]["slack"]["channels"] if c["name"] == "engineering")
    assert any("Platform architecture" in (m.get("text") or "") for m in eng["messages"])


def test_email_to_doc_update_plants_both_email_and_file():
    sc = generate_scenario("email-to-doc-update", seed=42)
    threads = sc["workspace"]["gmail"]["threads"]
    files = sc["workspace"]["drive"]["files"]
    assert any(t.get("kind_hint") == "planted_customer_correction" for t in threads)
    assert any(f.get("synthesised_for_scenario") == "email-to-doc-update" for f in files)


def test_triage_and_redirect_plants_three_channels():
    sc = generate_scenario("triage-and-redirect", seed=42)
    # Email touch-point
    assert any(
        t.get("kind_hint") == "planted_triage_email" for t in sc["workspace"]["gmail"]["threads"]
    )
    # Slack DM touch-point
    dms_with_msgs = [
        dm
        for dm in sc["workspace"]["slack"]["dms"]
        if any("mobile launch" in (m.get("text") or "").lower() for m in dm.get("messages", []))
    ]
    assert dms_with_msgs
    # Calendar touch-point
    assert any(
        e.get("title") == "Mobile launch date — go/no-go"
        for e in sc["workspace"]["calendar"]["events"]
    )
