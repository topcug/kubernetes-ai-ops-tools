"""Top-level workspace generator — composes all sub-systems into a coherent state."""

from __future__ import annotations

from typing import Any

from inboxr.calendar import generate_calendar
from inboxr.drive import generate_drive
from inboxr.gmail import generate_inbox
from inboxr.personas import generate_personas
from inboxr.slack import generate_slack
from inboxr.whatsapp import generate_whatsapp


def generate_workspace(
    seed: int = 42,
    difficulty: str = "medium",
    persona_count: int = 12,
    include_whatsapp: bool = True,
    company_domain: str | None = None,
) -> dict[str, Any]:
    """Generate a complete, coherent simulated workspace.

    Args:
        seed: RNG seed for determinism
        difficulty: "easy" | "medium" | "hard" | "crisis"
        persona_count: number of people in the org (including user)
        include_whatsapp: whether to include personal WhatsApp state
        company_domain: email domain override

    Returns:
        A dict containing personas and all linked environment state.
    """
    personas = generate_personas(
        count=persona_count,
        seed=seed,
        company_domain=company_domain,
        include_user=True,
    )

    workspace = {
        "meta": {
            "seed": seed,
            "difficulty": difficulty,
            "persona_count": persona_count,
            "user": personas[0].name,
            "user_email": personas[0].email,
            "company_domain": personas[0].email.split("@")[1],
        },
        "personas": [p.to_dict() for p in personas],
        "gmail": generate_inbox(personas, seed=seed, difficulty=difficulty),
        "slack": generate_slack(personas, seed=seed, difficulty=difficulty),
        "calendar": generate_calendar(personas, seed=seed, difficulty=difficulty),
        "drive": generate_drive(personas, seed=seed, difficulty=difficulty),
    }

    if include_whatsapp:
        workspace["whatsapp"] = generate_whatsapp(personas, seed=seed, difficulty=difficulty)

    return workspace
