"""Persona generation — coherent professional identities with roles, tone, and social graphs.

Each persona carries three layers of context:

1. Surface identity — name, email, role, department, slack handle, phone.
2. Communication style — tone register, working hours, timezone, message openers.
3. Social texture — both the bare relationship map (`relationships`, unchanged for
   backward compatibility) and the richer `relationship_history` list, which records
   past joint projects, conflicts, personal connections, and trust level. Scenarios
   and generators use this richer layer to produce stakeholder dynamics that feel
   lived-in: the CEO who still hasn't forgiven you for the Q2 miss, the designer you
   used to date, the PM you co-shipped three releases with.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

from faker import Faker

ROLES = [
    ("Engineering Manager", "engineering", "direct", ["VP Engineering", "PM", "Staff Engineer"]),
    ("Product Manager", "product", "diplomatic", ["VP Product", "Design Lead", "Eng Manager"]),
    ("Staff Engineer", "engineering", "technical", ["Eng Manager", "Architect"]),
    ("VP Engineering", "engineering", "strategic", ["CTO", "CEO"]),
    ("Designer", "design", "thoughtful", ["Design Lead", "PM"]),
    ("Design Lead", "design", "thoughtful", ["VP Product", "PM"]),
    ("Marketing Lead", "marketing", "persuasive", ["VP Marketing", "CEO"]),
    ("Customer Success Manager", "customer_success", "warm", ["VP Sales", "Support Lead"]),
    ("Account Executive", "sales", "assertive", ["VP Sales"]),
    ("Data Analyst", "data", "precise", ["Data Lead", "PM"]),
    ("Recruiter", "people", "friendly", ["Head of People"]),
    ("Head of People", "people", "measured", ["CEO"]),
    ("Finance Lead", "finance", "cautious", ["CFO"]),
    ("CEO", "executive", "visionary", []),
    ("CTO", "executive", "technical", ["CEO"]),
    ("Office Manager", "operations", "practical", ["Head of People"]),
]


TONES = {
    "direct": ["quick question — ", "FYI: ", "heads up — ", ""],
    "diplomatic": [
        "wanted to loop you in on ",
        "hope your week's going well — ",
        "curious about your take on ",
    ],
    "technical": ["looking at ", "debugging ", "spec for "],
    "strategic": ["stepping back: ", "zooming out — ", "thinking about how this fits with "],
    "thoughtful": [
        "been mulling over ",
        "a few thoughts on ",
        "something that's been on my mind: ",
    ],
    "persuasive": ["huge opportunity with ", "we should move on ", "strong case for "],
    "warm": ["hi! ", "hey you! ", "hope you're doing well 🙂 — "],
    "assertive": ["need a call on ", "ping me re: ", "moving on "],
    "precise": ["data shows ", "per the query results, ", "n=142: "],
    "friendly": ["hey! ", "quick one — ", "happy friday! "],
    "measured": ["a note on ", "circling back on ", "following up re "],
    "cautious": ["flagging: ", "concern on ", "before we commit, "],
    "visionary": ["thinking 18 months out: ", "the question is ", "imagine if we "],
    "practical": ["reminder: ", "FYI ", "just so you know — "],
}


# ---------------------------------------------------------------------------
# Relationship history catalogue
# ---------------------------------------------------------------------------
#
# Each entry is a template for a textured relationship fact that can be
# attached between two personas. Templates are grouped by kind so difficulty
# knobs can bias toward particular flavours (e.g. crisis scenarios lean on
# `conflict` and `stress` kinds to give the agent real stakeholder dynamics).

RELATIONSHIP_KINDS = {
    "collaboration": [
        "co-led the {project} launch in {year}; shipped on time",
        "paired on the {project} rewrite; it went well",
        "drove the {project} RFC together; aligned on trade-offs",
        "co-authored the {project} postmortem",
        "spent six months in the trenches on {project}; tight working rhythm",
    ],
    "conflict": [
        "disagreed publicly in the {project} review; tension has lingered",
        "pushed back hard on their plan for {project}; unresolved",
        "their {project} proposal was rejected largely on your feedback",
        "you inherited {project} after they were moved off it; they are cool about it",
        "they feel you took credit for {project}; you disagree",
    ],
    "mentorship": [
        "you interviewed and hired them onto the team",
        "they mentored you through your first quarter here",
        "you've been their career coach for the last 18 months",
        "they are your assigned mentor in the buddy program",
    ],
    "personal": [
        "kids go to the same school; see them at pickup",
        "you dated briefly before either of you joined the company",
        "gym buddies on Tuesdays",
        "neighbors; your partners are close friends",
        "they officiated your wedding",
        "you are godparent to their youngest",
        "climbing partners on weekends",
    ],
    "trust": [
        "they have covered for you during two on-calls; owe them one",
        "you trust their judgement on hiring unconditionally",
        "they have flaked on two of the last three commitments",
        "they read drafts of your docs before anyone else",
        "you route sensitive comp questions through them",
    ],
    "stress": [
        "they are on a PIP that you signed off on",
        "they are interviewing elsewhere; you suspect but haven't confirmed",
        "their last review from you was a 'meets' they expected an 'exceeds'",
        "they asked you for a promotion last month; you deferred",
        "you are quietly building a case to reorg their team",
    ],
}


@dataclass
class RelationshipFact:
    """A single textured fact about the tie between two personas.

    Kept intentionally compact — just enough for the agent or a downstream
    generator (email tone, Slack DM wording, meeting etiquette) to condition
    on. Facts are directional: `subject` holds this fact about `object`.
    """

    subject_id: str
    object_id: str
    kind: str  # collaboration | conflict | mentorship | personal | trust | stress
    note: str  # human-readable fact
    weight: float = 0.5  # 0..1 — how much this fact colours the relationship
    since_year: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Persona:
    """A single professional identity with full context."""

    id: str
    name: str
    email: str
    role: str
    department: str
    tone: str
    working_hours: tuple
    timezone: str
    relationships: dict[str, str] = field(default_factory=dict)
    slack_handle: str = ""
    phone: str = ""
    # New, richly-typed layer. Empty-by-default keeps every existing test and
    # downstream consumer working — callers that care about texture read this,
    # callers that don't just see the bare `relationships` map as before.
    relationship_history: list[RelationshipFact] = field(default_factory=list)
    trust_score: dict[str, float] = field(default_factory=dict)  # peer_id -> 0..1

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["working_hours"] = list(self.working_hours)
        d["relationship_history"] = [
            rf if isinstance(rf, dict) else rf.to_dict() for rf in self.relationship_history
        ]
        return d

    def opener(self, rng: random.Random) -> str:
        """Return a tone-appropriate message opener."""
        return rng.choice(TONES.get(self.tone, [""]))

    # Convenience readers for the richer texture layer. Generators use these
    # to tilt language — e.g. the email generator drops a warmer opener when
    # `dominant_flavour(other.id) == "personal"`.

    def facts_about(self, peer_id: str) -> list[RelationshipFact]:
        return [rf for rf in self.relationship_history if rf.object_id == peer_id]

    def dominant_flavour(self, peer_id: str) -> str | None:
        facts = self.facts_about(peer_id)
        if not facts:
            return None
        scored: dict[str, float] = {}
        for rf in facts:
            scored[rf.kind] = scored.get(rf.kind, 0.0) + rf.weight
        return max(scored.items(), key=lambda kv: kv[1])[0]


def generate_personas(
    count: int = 10,
    seed: int = 42,
    company_domain: str | None = None,
    include_user: bool = True,
) -> list[Persona]:
    """Generate a coherent set of personas with a plausible org structure.

    Args:
        count: total number of personas (including the user if include_user)
        seed: RNG seed for determinism
        company_domain: email domain (random if None)
        include_user: whether the first persona represents the user themselves

    Returns:
        List of Persona objects. First one is the user if include_user=True.
    """
    rng = random.Random(seed)
    fake = Faker()
    Faker.seed(seed)

    if company_domain is None:
        company_domain = f"{fake.word()}{fake.word()}.com".lower()

    timezones = ["America/Los_Angeles", "America/New_York", "Europe/London", "Europe/Berlin"]
    primary_tz = rng.choice(timezones)

    chosen_roles = rng.sample(ROLES, min(count, len(ROLES)))
    while len(chosen_roles) < count:
        chosen_roles.append(rng.choice(ROLES))

    personas: list[Persona] = []
    for i, (role, dept, tone, _reports_to) in enumerate(chosen_roles):
        name = fake.name()
        first, last = name.split()[0], name.split()[-1]
        email = f"{first.lower()}.{last.lower()}@{company_domain}"
        slack = f"@{first.lower()}{last[0].lower()}"

        # Most people in primary tz, a few scattered
        tz = primary_tz if rng.random() < 0.7 else rng.choice(timezones)

        # Working hours: mostly 9-6, some variation
        start = rng.choice([8, 9, 9, 9, 10])
        end = start + rng.choice([8, 8, 9, 10])

        p = Persona(
            id=f"user_{i:03d}" if (include_user and i == 0) else f"p_{i:03d}",
            name=name,
            email=email,
            role=role,
            department=dept,
            tone=tone,
            working_hours=(start, end),
            timezone=tz,
            slack_handle=slack,
            phone=fake.phone_number(),
        )
        personas.append(p)

    # Build relationships (who reports to whom, who collaborates)
    for i, p in enumerate(personas):
        rels: dict[str, str] = {}
        # Each persona has 2-5 collaborators
        n_rels = rng.randint(2, min(5, len(personas) - 1))
        others = [o for o in personas if o.id != p.id]
        for collab in rng.sample(others, n_rels):
            relation = rng.choice(["collaborator", "manager", "report", "cross_functional"])
            rels[collab.id] = relation
        p.relationships = rels

    # Layer the richer textured history on top of the bare graph.
    _attach_relationship_history(personas, rng)

    return personas


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


# Projects used to seed relationship histories. Overlaps intentionally with
# the project pool used by gmail/slack/drive so the facts feel cross-referenced
# rather than free-floating.
_HISTORY_PROJECTS = [
    "Atlas",
    "Phoenix",
    "Pricing",
    "Onboarding",
    "Mobile",
    "Platform",
    "Growth",
    "Q2 planning",
    "Mobile launch",
    "Customer Summit",
    "the data warehouse migration",
    "the API deprecation",
    "the brand refresh",
    "the holiday campaign",
]


def _attach_relationship_history(personas: list[Persona], rng: random.Random) -> None:
    """Populate `relationship_history` and `trust_score` for every persona.

    Rules of thumb the helper encodes:

    - Managers and reports always have at least one mentorship fact.
    - Collaborators tend to accumulate `collaboration` facts, sometimes with
      a `conflict` underlay (past disagreement on a specific project).
    - A small fraction of ties have a `personal` flavour — kids at the same
      school, climbing partners, an ex. This is what makes scenarios like
      "draft a reschedule without burning bridges" non-trivial.
    - `stress` facts are rare but high-weight — they reshape how an agent
      should phrase a message if it notices them.
    """

    if len(personas) < 2:
        return

    # Each tie direction gets between one and three facts. Two-way ties have
    # independent facts on each side (Alice's view of Bob != Bob's view of
    # Alice) which lets scenarios exploit asymmetry.
    for p in personas:
        for peer_id, bare_relation in p.relationships.items():
            n_facts = rng.randint(1, 3)
            kinds = _kinds_for_relation(bare_relation, rng)
            chosen_kinds = rng.choices(kinds, k=n_facts)

            for kind in chosen_kinds:
                template = rng.choice(RELATIONSHIP_KINDS[kind])
                note = template.format(
                    project=rng.choice(_HISTORY_PROJECTS),
                    year=rng.choice([2022, 2023, 2024, 2025]),
                )
                weight = {
                    "collaboration": rng.uniform(0.3, 0.7),
                    "conflict": rng.uniform(0.5, 0.9),
                    "mentorship": rng.uniform(0.4, 0.8),
                    "personal": rng.uniform(0.4, 0.9),
                    "trust": rng.uniform(0.3, 0.8),
                    "stress": rng.uniform(0.6, 0.95),
                }[kind]
                p.relationship_history.append(
                    RelationshipFact(
                        subject_id=p.id,
                        object_id=peer_id,
                        kind=kind,
                        note=note,
                        weight=round(weight, 2),
                        since_year=rng.choice([2022, 2023, 2024, 2025]),
                    )
                )

            # Trust score is a cheap scalar derived from the fact mix so that
            # downstream consumers (e.g. email tone or meeting decline logic)
            # can make a quick call without scanning the full list.
            p.trust_score[peer_id] = _derive_trust(p.facts_about(peer_id))


def _kinds_for_relation(bare_relation: str, rng: random.Random) -> list[str]:
    """Return a plausible pool of fact kinds for a given bare relation label.

    Skewed so the most common flavour lines up with the label but leaves room
    for surprises — a 'report' can still have a past conflict fact, which is
    exactly the kind of texture scenarios need.
    """
    if bare_relation == "manager":
        return ["mentorship", "mentorship", "trust", "stress", "collaboration"]
    if bare_relation == "report":
        return ["mentorship", "collaboration", "trust", "stress", "conflict"]
    if bare_relation == "collaborator":
        return ["collaboration", "collaboration", "trust", "conflict", "personal"]
    if bare_relation == "cross_functional":
        return ["collaboration", "conflict", "trust", "personal"]
    return ["collaboration", "trust"]


def _derive_trust(facts: list[RelationshipFact]) -> float:
    """Collapse a list of relationship facts into a single 0..1 trust score.

    Positive kinds push the score up, negative kinds (conflict, stress) pull
    it down. Starts at 0.5 so personas with no shared history land on neutral
    rather than extreme either way.
    """
    if not facts:
        return 0.5
    score = 0.5
    for rf in facts:
        bump = {
            "collaboration": 0.10,
            "mentorship": 0.12,
            "trust": 0.10,
            "personal": 0.08,
            "conflict": -0.15,
            "stress": -0.20,
        }.get(rf.kind, 0.0)
        score += bump * rf.weight
    return round(max(0.0, min(1.0, score)), 2)
