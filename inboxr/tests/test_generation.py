"""Smoke + determinism tests for Inboxr."""

import json

from inboxr import (
    SCENARIO_TEMPLATES,
    generate_personas,
    generate_scenario,
    generate_workspace,
)


def test_personas_deterministic():
    a = [p.to_dict() for p in generate_personas(count=8, seed=123)]
    b = [p.to_dict() for p in generate_personas(count=8, seed=123)]
    assert a == b


def test_personas_different_seeds_differ():
    a = [p.name for p in generate_personas(count=8, seed=1)]
    b = [p.name for p in generate_personas(count=8, seed=2)]
    assert a != b


def test_workspace_has_all_systems():
    ws = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    for key in ("meta", "personas", "gmail", "slack", "calendar", "drive", "whatsapp"):
        assert key in ws, f"missing {key}"


def test_difficulty_scales_volume():
    easy = generate_workspace(seed=42, difficulty="easy", persona_count=6)
    crisis = generate_workspace(seed=42, difficulty="crisis", persona_count=6)
    assert crisis["gmail"]["summary"]["total_threads"] > easy["gmail"]["summary"]["total_threads"]
    assert crisis["drive"]["summary"]["total_files"] > easy["drive"]["summary"]["total_files"]


def test_all_scenarios_generate():
    for name in SCENARIO_TEMPLATES:
        sc = generate_scenario(name, seed=42)
        assert sc["template"] == name
        assert sc["task"]
        assert sc["success_criteria"]
        assert "gmail" in sc["workspace"]


def test_monday_morning_plants_urgent_email():
    sc = generate_scenario("monday-morning", seed=42)
    threads = sc["workspace"]["gmail"]["threads"]
    planted = [t for t in threads if t.get("kind_hint") == "planted_urgent"]
    assert len(planted) == 1


def test_workspace_serializes_to_json():
    ws = generate_workspace(seed=7, difficulty="medium", persona_count=5)
    s = json.dumps(ws)
    assert len(s) > 1000
