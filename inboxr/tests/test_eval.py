"""Tests for the evaluation harness."""

import json

from inboxr import (
    AgentAction,
    MockAgent,
    WorkspaceTools,
    build_agent,
    generate_scenario,
    run_eval,
)
from inboxr.eval import _parse_action

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def test_workspace_tools_read_email():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    first_thread = sc["workspace"]["gmail"]["threads"][0]
    result = tools.apply({"name": "read_email", "arguments": {"thread_id": first_thread["id"]}})
    assert result["id"] == first_thread["id"]
    # The read_email tool strips eval-only hints
    for msg in result["messages"]:
        assert "kind_hint" not in msg


def test_workspace_tools_unknown_tool_returns_error():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    result = tools.apply({"name": "launch_nukes", "arguments": {}})
    assert "error" in result


def test_workspace_tools_bad_args_returns_error():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    result = tools.apply({"name": "read_email", "arguments": {"wrong_arg": 1}})
    assert "error" in result


def test_workspace_tools_drafts_are_recorded():
    sc = generate_scenario("monday-morning", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    tools.apply(
        {"name": "draft_message", "arguments": {"to": "x", "channel": "email", "body": "hi"}}
    )
    assert len(tools.drafts) == 1
    assert tools.drafts[0]["body"] == "hi"


def test_workspace_tools_search_drive():
    sc = generate_scenario("new-hire", seed=42)
    tools = WorkspaceTools(sc["workspace"])
    result = tools.apply({"name": "search_drive", "arguments": {"query": "onboarding"}})
    # new-hire scenario plants an onboarding doc
    assert result["count"] >= 1


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_action_valid_json():
    raw = '{"thought": "t", "tool_calls": [{"name": "list_emails", "arguments": {}}], "final_answer": null}'
    action = _parse_action(raw)
    assert action.thought == "t"
    assert action.tool_calls[0]["name"] == "list_emails"
    assert action.final_answer is None


def test_parse_action_garbage_becomes_final_answer():
    action = _parse_action("not json at all")
    assert action.is_terminal()
    assert action.final_answer == "not json at all"


def test_parse_action_terminal():
    raw = '{"thought": "done", "tool_calls": [], "final_answer": "all done"}'
    action = _parse_action(raw)
    assert action.is_terminal()
    assert action.final_answer == "all done"


# ---------------------------------------------------------------------------
# End-to-end eval with MockAgent
# ---------------------------------------------------------------------------


def test_run_eval_with_mock_agent_produces_result():
    sc = generate_scenario("monday-morning", seed=42)
    result = run_eval(sc, MockAgent(), max_steps=10)
    assert result.template == "monday-morning"
    assert len(result.trajectory) >= 1
    assert result.stopped_reason in ("terminal", "max_steps")


def test_run_eval_terminates_on_final_answer():
    sc = generate_scenario("monday-morning", seed=42)
    result = run_eval(sc, MockAgent(), max_steps=20)
    assert result.stopped_reason == "terminal"
    # MockAgent has 6 steps in its script
    assert len(result.trajectory) <= 6


def test_run_eval_respects_max_steps():
    class NeverStopAgent:
        name = "infinite"

        def act(self, observation):
            return AgentAction(
                thought="more", tool_calls=[{"name": "list_emails", "arguments": {}}]
            )

    sc = generate_scenario("monday-morning", seed=42)
    result = run_eval(sc, NeverStopAgent(), max_steps=3)
    assert result.stopped_reason == "max_steps"
    assert len(result.trajectory) == 3


def test_run_eval_handles_agent_errors():
    class BrokenAgent:
        name = "broken"

        def act(self, observation):
            raise RuntimeError("kaboom")

    sc = generate_scenario("monday-morning", seed=42)
    result = run_eval(sc, BrokenAgent(), max_steps=5)
    assert result.stopped_reason == "error"
    assert "kaboom" in result.trajectory[-1].thought


def test_eval_result_is_json_serializable():
    sc = generate_scenario("monday-morning", seed=42)
    result = run_eval(sc, MockAgent(), max_steps=10)
    s = json.dumps(result.to_dict())
    assert len(s) > 500


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------


def test_rubric_heuristic_gives_pass_fail():
    sc = generate_scenario("monday-morning", seed=42)
    result = run_eval(sc, MockAgent(), max_steps=10)
    # Every criterion must appear in the scores
    criteria_in = set(sc["success_criteria"])
    criteria_out = {c["criterion"] for c in result.criteria_scores}
    assert criteria_in == criteria_out
    # Score must be a ratio in [0, 1]
    assert 0.0 <= result.score <= 1.0


def test_rubric_rewards_drafting():
    """An agent that drafts should outscore one that does nothing on draft criteria."""

    class SilentAgent:
        name = "silent"

        def act(self, observation):
            return AgentAction(final_answer="done")

    sc = generate_scenario("monday-morning", seed=42)
    silent_score = run_eval(sc, SilentAgent(), max_steps=5).score
    mock_score = run_eval(sc, MockAgent(), max_steps=10).score
    assert mock_score > silent_score


# ---------------------------------------------------------------------------
# Agent builder
# ---------------------------------------------------------------------------


def test_build_agent_mock():
    agent = build_agent("mock")
    assert agent.name == "mock"


def test_build_agent_rejects_bad_spec():
    import pytest

    with pytest.raises(ValueError):
        build_agent("not-a-spec")
    with pytest.raises(ValueError):
        build_agent("unknown:model")
