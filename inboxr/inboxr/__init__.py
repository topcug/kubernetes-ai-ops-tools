"""Inboxr — synthetic workspace generator for AI agent training and evaluation."""

from inboxr.calendar import generate_calendar
from inboxr.consistency import (
    ConsistencyReport,
    ReferenceGraph,
    Violation,
    build_reference_graph,
)
from inboxr.consistency import (
    check as check_consistency,
)
from inboxr.consistency import (
    repair as repair_consistency,
)
from inboxr.drive import generate_drive
from inboxr.eval import (
    Agent,
    AgentAction,
    AnthropicAgent,
    EvalResult,
    MockAgent,
    OpenAIAgent,
    Rubric,
    WorkspaceTools,
    build_agent,
    run_eval,
)
from inboxr.gmail import generate_inbox
from inboxr.personas import Persona, generate_personas
from inboxr.scenarios import SCENARIO_TEMPLATES, generate_scenario
from inboxr.slack import generate_slack
from inboxr.whatsapp import generate_whatsapp
from inboxr.workspace import generate_workspace

__version__ = "0.1.0"

__all__ = [
    "Persona",
    "generate_personas",
    "generate_inbox",
    "generate_slack",
    "generate_calendar",
    "generate_drive",
    "generate_whatsapp",
    "generate_scenario",
    "generate_workspace",
    "SCENARIO_TEMPLATES",
    "check_consistency",
    "repair_consistency",
    "build_reference_graph",
    "ConsistencyReport",
    "ReferenceGraph",
    "Violation",
    "run_eval",
    "build_agent",
    "Agent",
    "MockAgent",
    "OpenAIAgent",
    "AnthropicAgent",
    "Rubric",
    "WorkspaceTools",
    "AgentAction",
    "EvalResult",
]
