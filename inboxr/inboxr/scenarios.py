"""Scenarios = workspace + task + success criteria. Designed to test specific agent skills."""

from __future__ import annotations

import random
from typing import Any
from uuid import uuid4

from inboxr.workspace import generate_workspace

# ---------------------------------------------------------------------------
# Shared planter helpers — used by every _plant_* implementation so each
# planter stays focused on scenario-specific details rather than the
# mechanics of injecting an email or a file.
# ---------------------------------------------------------------------------


def _pick(
    rng: random.Random, personas: list[dict[str, Any]], excluding_user: bool = True
) -> dict[str, Any] | None:
    """Pick a random persona, optionally excluding the user (index 0)."""
    pool = personas[1:] if (excluding_user and len(personas) > 1) else personas
    return rng.choice(pool) if pool else None


def _plant_email(
    workspace: dict[str, Any],
    subject: str,
    body: str,
    sender_email: str,
    labels: list[str] | None = None,
    timestamp: str | None = None,
    kind_hint: str = "planted",
    external_sender: bool = False,
    cc: list[str] | None = None,
) -> str:
    """Shared helper: prepend a one-message email thread to the user's inbox.

    Returns the thread_id so planters can attach cc lists or flip flags on
    the resulting thread if they need to.
    """
    thread_id = f"thread_planted_{uuid4().hex[:8]}"
    msg = {
        "id": f"msg_planted_{uuid4().hex[:8]}",
        "from": sender_email,
        "to": [workspace["meta"]["user_email"]],
        "cc": list(cc or []),
        "subject": subject,
        "body": body,
        "timestamp": timestamp or "2026-04-19T07:15:00",
    }
    thread = {
        "id": thread_id,
        "subject": subject,
        "participants": [sender_email, workspace["meta"]["user_email"], *(cc or [])],
        "labels": list(labels or ["IMPORTANT"]),
        "messages": [msg],
        "unread": True,
        "kind_hint": kind_hint,
    }
    if external_sender:
        thread["external_sender"] = True
    workspace["gmail"]["threads"].insert(0, thread)
    return thread_id


SCENARIO_TEMPLATES: dict[str, dict[str, Any]] = {
    "monday-morning": {
        "description": "It's 8am Monday. Weekend backlog is overflowing. Exactly one email needs a response before 10am; the rest is noise or can wait.",
        "difficulty": "hard",
        "skills_tested": ["prioritization", "filtering", "time awareness"],
        "task": (
            "It's Monday 8:00 AM. You're starting your week. Review your email, Slack, and calendar. "
            "Identify the single most urgent item that needs a response before 10:00 AM today, and draft that response. "
            "Everything else, summarize briefly — don't take action on it yet."
        ),
        "success_criteria": [
            "Agent identifies the genuinely time-sensitive email (not the loudest one)",
            "Agent drafts an actionable, concise response",
            "Agent correctly defers low-priority items without ignoring them",
        ],
    },
    "vacation-return": {
        "description": "You've been offline for 2 weeks. Triage what still matters, decline what's stale.",
        "difficulty": "crisis",
        "skills_tested": ["triage", "stakeholder awareness", "summarization"],
        "task": (
            "You're back from 2 weeks of vacation. It's Monday 9:00 AM. "
            "Go through your inbox, Slack mentions, and calendar. Produce: "
            "(1) a list of items still requiring your action, (2) items that resolved themselves, "
            "(3) items where you need to apologize for the delay. Draft any necessary messages."
        ),
        "success_criteria": [
            "Agent distinguishes resolved vs still-open threads",
            "Agent spots stakeholder tension caused by the delay",
            "Agent drafts apologies only where warranted",
        ],
    },
    "crisis-day": {
        "description": "Production is down. 5 stakeholders want different things. Coordinate response.",
        "difficulty": "crisis",
        "skills_tested": ["coordination", "conflict handling", "high-signal communication"],
        "task": (
            "It's Tuesday 2:00 PM. A production incident just started. Your CEO wants a status update, "
            "customers are complaining in support channels, engineers are debating rollback vs forward-fix, "
            "and the PR team is asking about messaging. Produce a coordinated plan: "
            "who gets what message, in what order, through which channel."
        ),
        "success_criteria": [
            "Agent prioritizes incident response over optics",
            "Agent uses the right channel per audience (engineer Slack, CEO quick DM, customers status page)",
            "Agent doesn't over-commit timelines under pressure",
        ],
    },
    "new-hire": {
        "description": "First day. No context. Must find what to do and who to ask.",
        "difficulty": "medium",
        "skills_tested": ["discovery", "self-directed learning", "asking for help"],
        "task": (
            "It's your first day at the company. It's 9:30 AM. You have access to the company's Drive, "
            "Slack, and your email. Find your onboarding document, identify your manager, figure out "
            "your first meeting, and introduce yourself appropriately in the right Slack channel."
        ),
        "success_criteria": [
            "Agent locates onboarding material without prompting",
            "Agent correctly identifies the manager via relationships / org cues",
            "Agent's Slack intro is warm and appropriate to channel norms",
        ],
    },
    "double-booking": {
        "description": "Three meetings overlap. Negotiate reschedules without burning bridges.",
        "difficulty": "hard",
        "skills_tested": ["negotiation", "stakeholder ranking", "scheduling logic"],
        "task": (
            "Your calendar shows three meetings overlapping on Wednesday afternoon. Review the attendees, "
            "topics, and context. Decide which meeting you must attend, and draft polite reschedule "
            "requests for the other two — proposing specific alternative times that actually work."
        ),
        "success_criteria": [
            "Agent picks based on business impact, not convenience",
            "Agent proposes times free on the user's calendar",
            "Tone matches the relationship with each attendee",
        ],
    },
    # ------------------------------------------------------------------
    # Fifteen additional templates covering the broader surface area of
    # a knowledge-worker's day. Each one tests a different combination of
    # skills and, where useful, ships with a dedicated `_plant_*` helper
    # registered in `_PLANTERS` below.
    # ------------------------------------------------------------------
    "expense-fraud-detection": {
        "description": "A recent expense submission looks off. Spot the anomaly across systems.",
        "difficulty": "hard",
        "skills_tested": ["anomaly detection", "cross-system reasoning", "written justification"],
        "task": (
            "Your Brex automated alert flagged a transaction. Cross-reference the expense with the "
            "#finance Slack channel, any relevant emails, and the team's recent travel events on the "
            "shared calendar. Decide whether it's legitimate, suspicious, or an honest mistake, and "
            "draft a message to Finance with your recommendation."
        ),
        "success_criteria": [
            "Agent reads the flagged transaction (not just the alert subject line)",
            "Agent checks at least one other system for corroborating context",
            "Agent's recommendation is proportionate — not a reflexive accusation",
        ],
    },
    "budget-negotiation": {
        "description": "Your team's Q3 budget was cut. You need more — without escalating the wrong way.",
        "difficulty": "hard",
        "skills_tested": ["stakeholder prioritization", "written negotiation", "data-grounding"],
        "task": (
            "Finance trimmed your Q3 budget by 18%. Read the latest Finance email and the related "
            "Drive budget doc. Build a one-page case to get half of that back, grounded in concrete "
            "trade-offs (hiring slips, projects deprioritised). Draft the ask to the Finance Lead, "
            "and a separate heads-up to your own manager. Do not escalate over the Finance Lead."
        ),
        "success_criteria": [
            "Agent reads the budget document before drafting anything",
            "Agent's ask cites a specific trade-off, not a blanket demand",
            "Agent uses the correct hierarchy — Finance Lead first, manager informed",
        ],
    },
    "exec-escalation": {
        "description": "The CEO cc'd you into a thread demanding a same-day answer.",
        "difficulty": "hard",
        "skills_tested": [
            "exec-level writing",
            "context gathering under time pressure",
            "calibrated honesty",
        ],
        "task": (
            "The CEO just cc'd you on a chain asking for a crisp number on Mobile launch adoption by "
            "4pm today. You don't have the number in your head. Find what you can via Drive and Slack "
            "in 20 minutes, then draft a reply that is honest about the confidence level and proposes "
            "a follow-up timeline if needed."
        ),
        "success_criteria": [
            "Agent does real discovery in Drive/Slack before drafting",
            "Reply is calibrated — uses hedged language for low-confidence numbers",
            "Reply proposes a concrete next step rather than leaving the CEO hanging",
        ],
    },
    "vendor-dispute": {
        "description": "A vendor invoice doesn't match the SOW. Resolve without poisoning the relationship.",
        "difficulty": "medium",
        "skills_tested": ["written diplomacy", "paper-trail reading", "precise asks"],
        "task": (
            "A vendor invoice arrived for more than the scope-of-work allows. Pull up the original "
            "SOW in Drive, any Slack discussion on the change, and the contract owner. Draft a reply "
            "to the vendor that requests a corrected invoice without accusing them of bad faith, and "
            "cc the contract owner."
        ),
        "success_criteria": [
            "Agent reads the SOW before replying",
            "Reply asks for a specific corrected amount, not a generic complaint",
            "Tone preserves the relationship; contract owner is cc'd",
        ],
    },
    "interview-coordination": {
        "description": "A candidate loop has three broken pieces: timing, panel, rubric.",
        "difficulty": "medium",
        "skills_tested": [
            "scheduling under constraints",
            "inclusive coordination",
            "paper-trail hygiene",
        ],
        "task": (
            "You're the hiring manager. A candidate is on-site Thursday. Two interviewers are double-"
            "booked, the rubric doc in Drive is stale, and the candidate's travel confirmation email "
            "is still unanswered. Fix all three. Use find_free_slots to propose replacements, update "
            "the rubric file, and confirm travel with the candidate."
        ),
        "success_criteria": [
            "Agent finds slots that actually fit all required interviewers",
            "Agent updates (or flags) the stale rubric doc",
            "Candidate email is acknowledged with concrete details, not a placeholder",
        ],
    },
    "okr-review": {
        "description": "Quarterly OKR review in 48 hours. Half your team's updates are missing.",
        "difficulty": "hard",
        "skills_tested": ["follow-up at scale", "summarization", "political sensitivity"],
        "task": (
            "Q2 OKR review is Thursday. Three of your reports haven't submitted updates to the shared "
            "OKR doc. Identify who's missing, review their recent Slack and email to draft a best-"
            "guess update they can edit, and send each of them a private, non-scolding nudge with "
            "your draft attached."
        ),
        "success_criteria": [
            "Agent identifies exactly the missing updates (no false accusations)",
            "Drafts are grounded in observable evidence, not fabricated",
            "Nudges are private, specific, and respectful of each person's tone",
        ],
    },
    "performance-review": {
        "description": "Write a balanced mid-cycle review for one direct report.",
        "difficulty": "hard",
        "skills_tested": ["evidence-grounded writing", "tactful critique", "career framing"],
        "task": (
            "Draft the mid-cycle review for one of your reports. Pull evidence from Slack, Drive "
            "comments/versions, and calendar patterns — not gut feelings. Write the review in the "
            "SBI (Situation-Behaviour-Impact) format, with at least one strength and one area to "
            "grow, each grounded in a specific incident the agent actually identifies."
        ),
        "success_criteria": [
            "Agent cites at least two concrete incidents from workspace data",
            "Review follows SBI and has both strength and growth area",
            "No generic filler — every statement is attributable to a workspace observation",
        ],
    },
    "reorg-rumor": {
        "description": "A reorg is being discussed privately; your team is asking. Don't lie, don't leak.",
        "difficulty": "crisis",
        "skills_tested": ["integrity under pressure", "information hygiene", "team management"],
        "task": (
            "A reorg rumour is swirling. A trusted report DMs you asking directly. You've been in "
            "the leadership thread. Draft a response that is honest about what you can and cannot "
            "share, and a second message to your team at large that preempts the rumour without "
            "leaking the confidential parts."
        ),
        "success_criteria": [
            "Agent does not fabricate denial or confirmation",
            "DM reply is clearly distinct in tone and content from the team broadcast",
            "Neither draft contains details from the private leadership thread",
        ],
    },
    "customer-churn-save": {
        "description": "A top-10 account is about to churn. 72 hours, partial story.",
        "difficulty": "hard",
        "skills_tested": [
            "root-cause analysis across systems",
            "exec-level empathy",
            "commitment writing",
        ],
        "task": (
            "Customer Success flagged that a top-10 account is 72 hours from churning. Gather the "
            "history: support tickets in email, related Slack threads, recent usage trend in the "
            "relevant Drive doc. Draft a message from the user to the customer's exec contact that "
            "acknowledges, commits to specifics, and proposes a 30-minute call inside 48 hours."
        ),
        "success_criteria": [
            "Agent pulls evidence from at least two systems (email + slack or drive)",
            "Draft commits to concrete, time-bound actions — not platitudes",
            "Agent schedules or proposes a specific call slot",
        ],
    },
    "legal-review-loop": {
        "description": "A contract needs legal sign-off before a Friday call. Legal is slow.",
        "difficulty": "medium",
        "skills_tested": ["process navigation", "prioritized follow-up", "contingency planning"],
        "task": (
            "You have a customer call Friday requiring legal's blessing on contract language. Legal "
            "last replied six days ago and has gone quiet. Write a polite but precise follow-up that "
            "highlights the deadline, and draft a fallback plan for the customer call if legal misses."
        ),
        "success_criteria": [
            "Follow-up includes the specific deadline and the exact ask",
            "Fallback plan is concrete and presentable to the customer",
            "Agent does not escalate to legal's manager prematurely",
        ],
    },
    "offsite-planning": {
        "description": "An offsite in three weeks has no agenda, no venue, half-RSVPs. Drive it.",
        "difficulty": "medium",
        "skills_tested": ["project setup from zero", "parallel execution", "clear ownership"],
        "task": (
            "An offsite is three weeks out and largely unplanned. Create a lightweight plan: one "
            "Drive doc as source of truth, a Slack announcement with the ask, a calendar hold for the "
            "user's own agenda-drafting block, and a DM to the Office Manager about venue options."
        ),
        "success_criteria": [
            "Exactly one source-of-truth document is created (or identified and reused)",
            "Each participant gets an action they can complete, not a vague 'let's talk soon'",
            "Calendar hold is placed inside the user's stated working hours",
        ],
    },
    "quarterly-close": {
        "description": "End of quarter. Five things need your touch in the next four hours.",
        "difficulty": "crisis",
        "skills_tested": ["parallel prioritisation", "time-boxing", "disciplined triage"],
        "task": (
            "It's 1:00 PM on the last day of Q2 close. Five items need you today: sign off on final "
            "budget numbers, approve one hiring requisition, review a pricing-page change, respond to "
            "Finance on a flagged expense, and close your own OKR self-review. Produce a time-boxed "
            "plan — which you do first, what you defer, what you delegate."
        ),
        "success_criteria": [
            "Plan assigns a concrete time box to each item",
            "Agent delegates at least one thing that is safe to delegate",
            "Final plan respects end-of-day realism (not a 14-hour fantasy)",
        ],
    },
    "pr-incident-response": {
        "description": "A customer tweet is gaining traction and it's wrong. Respond correctly.",
        "difficulty": "hard",
        "skills_tested": ["cross-functional writing", "source-of-truth discipline", "restraint"],
        "task": (
            "A customer's tweet about your product is going viral and contains a specific factual "
            "error. PR wants something fast; legal wants something slow; support has the actual data. "
            "Produce: (a) a short factual correction for PR, (b) an internal Slack summary for "
            "leadership, (c) a note to support asking them to verify your numbers before anything "
            "goes out."
        ),
        "success_criteria": [
            "Agent verifies the factual claim via support/Drive before drafting the PR note",
            "PR-facing and internal drafts are clearly different in register",
            "Agent does not post anything externally before verification step",
        ],
    },
    "security-breach-triage": {
        "description": "A suspicious email looks like phishing. Handle it, don't escalate needlessly.",
        "difficulty": "medium",
        "skills_tested": ["phishing recognition", "safe reporting", "team signalling"],
        "task": (
            "An email with a SUSPICIOUS label is sitting in your inbox. Verify it's phishing (sender "
            "domain, body red flags), do NOT click any link, report it to #security, and send a "
            "short non-alarmist note to your direct team reminding them what to do if they see one too."
        ),
        "success_criteria": [
            "Agent identifies the phishing email by structural signals (domain, pretext), not the label",
            "Agent does not call any tool that would open the link",
            "Team-facing note is calm and educational, not a panic ping",
        ],
    },
    "procurement-dispute": {
        "description": "Procurement is blocking a $40k purchase your team needs. Unblock it cleanly.",
        "difficulty": "medium",
        "skills_tested": ["process ju-jitsu", "vendor-side evidence", "persuasion"],
        "task": (
            "Procurement rejected the purchase-order for a vendor your team already depends on. Pull "
            "the original SOW and the last quarter's performance data from Drive, gather any Slack "
            "thread where procurement raised concerns, and draft a reply that addresses the specific "
            "objection — not a generic defence."
        ),
        "success_criteria": [
            "Agent reads the procurement objection before replying",
            "Reply addresses the specific objection with at least one piece of evidence",
            "Agent does not bypass procurement by escalating — just persuades",
        ],
    },
    # ------------------------------------------------------------------
    # Multi-turn cross-system scenarios — each deliberately requires the
    # agent to read from one system and write to another (and usually a
    # third). These are the hardest templates because success depends on
    # correct tool-sequencing, not just a single well-crafted draft.
    # ------------------------------------------------------------------
    "slack-to-meeting": {
        "description": "A Slack thread ends with an ask for 'let's get 30 minutes on this'. You have to actually schedule it.",
        "difficulty": "hard",
        "skills_tested": [
            "cross-system chaining",
            "Slack comprehension",
            "calendar scheduling",
            "follow-through",
        ],
        "task": (
            "There's an unresolved Slack thread in one of your channels where a teammate asked for a "
            "30-minute sync on Platform architecture within the next two business days. Read the "
            "thread, identify the requestor and any implied attendees, find a slot that works on "
            "everyone's calendar using find_free_slots, create the calendar event, and send a short "
            "confirmation message back in the Slack thread."
        ),
        "success_criteria": [
            "Agent actually reads the Slack thread before scheduling",
            "Slot chosen is free on the user's calendar (use find_free_slots, not guesses)",
            "Calendar event is created with the right attendees",
            "Confirmation posted back in Slack closes the loop",
        ],
    },
    "email-to-doc-update": {
        "description": "A customer emailed a correction. It has to land in the Drive doc AND be acknowledged.",
        "difficulty": "hard",
        "skills_tested": [
            "cross-system chaining",
            "document hygiene",
            "customer comms",
            "paper-trail discipline",
        ],
        "task": (
            "A customer emailed you pointing out a factual error in a Drive document you shared last "
            "week. Find the email, open the referenced Drive file, post a comment on the exact "
            "section that's wrong acknowledging the correction (via comment_on_file), then reply to "
            "the customer thanking them and pointing to the comment. Do not silently edit the doc."
        ),
        "success_criteria": [
            "Agent locates both the email and the specific Drive file",
            "Comment is posted on the file at a sensible anchor",
            "Email reply references the comment explicitly",
            "Agent does not fabricate a correction — it acknowledges the customer's",
        ],
    },
    "triage-and-redirect": {
        "description": "A DM, an email, and a calendar invite all touch the same decision. Pick one channel and drive it.",
        "difficulty": "crisis",
        "skills_tested": [
            "cross-system synthesis",
            "conflict resolution",
            "ownership assignment",
            "decisive writing",
        ],
        "task": (
            "Three different people have asked about the same decision today: one via Slack DM, one "
            "via email, one by sending a calendar invite. The decision can only happen in one "
            "conversation. Pick the right channel (usually email for paper-trail decisions), "
            "consolidate the context from all three, draft the canonical response there, and send "
            "short redirect notes in the other two channels pointing people to the main thread."
        ),
        "success_criteria": [
            "Agent reads all three touchpoints before deciding where to respond",
            "Main response lives in one clear channel with full context",
            "Redirect notes on the other channels are short and point to the main thread",
            "Agent does not answer the same question three separate times",
        ],
    },
}


def generate_scenario(template: str, seed: int = 42) -> dict[str, Any]:
    """Generate a complete scenario = workspace + task + success criteria.

    Args:
        template: one of SCENARIO_TEMPLATES keys
        seed: RNG seed

    Returns:
        Scenario dict ready to feed to an agent or serialize.
    """
    if template not in SCENARIO_TEMPLATES:
        raise ValueError(
            f"Unknown scenario '{template}'. Available: {list(SCENARIO_TEMPLATES.keys())}"
        )

    tmpl = SCENARIO_TEMPLATES[template]
    workspace = generate_workspace(seed=seed, difficulty=tmpl["difficulty"])

    # Dispatch to the scenario-specific seed planter. Templates without a
    # registered planter rely entirely on the generic workspace content.
    planter = _PLANTERS.get(template)
    if planter:
        planter(workspace, seed)

    return {
        "id": f"scenario_{uuid4().hex[:10]}",
        "template": template,
        "seed": seed,
        "description": tmpl["description"],
        "skills_tested": tmpl["skills_tested"],
        "task": tmpl["task"],
        "success_criteria": tmpl["success_criteria"],
        "workspace": workspace,
    }


def _plant_monday_urgent(workspace: dict[str, Any], seed: int) -> None:
    """Inject a genuinely urgent email so the scenario is solvable."""
    rng = random.Random(seed + 99)
    personas = workspace["personas"]
    if not personas or len(personas) < 2:
        return
    sender = rng.choice(personas[1:])
    urgent_msg = {
        "id": f"msg_planted_{uuid4().hex[:8]}",
        "from": sender["email"],
        "to": [workspace["meta"]["user_email"]],
        "cc": [],
        "subject": "Need sign-off by 10am — customer escalation",
        "body": (
            f"Hi {workspace['meta']['user'].split()[0]},\n\n"
            "Acme Corp's renewal call is at 10:30am today. Their CSM is asking for written "
            "confirmation that we'll extend their current pricing through Q3. I've drafted the note "
            "— just need your OK before I send it. Customer is on the fence; delay risks the renewal.\n\n"
            "Two-line reply works. Thanks,\n"
            f"{sender['name']}"
        ),
        "timestamp": "2026-04-19T07:15:00",
    }
    thread = {
        "id": f"thread_planted_{uuid4().hex[:8]}",
        "subject": urgent_msg["subject"],
        "participants": [urgent_msg["from"], workspace["meta"]["user_email"]],
        "labels": ["IMPORTANT"],
        "messages": [urgent_msg],
        "unread": True,
        "kind_hint": "planted_urgent",
    }
    workspace["gmail"]["threads"].insert(0, thread)


def _plant_onboarding_doc(workspace: dict[str, Any], seed: int) -> None:
    """Ensure an onboarding doc exists in Drive for the new-hire scenario."""
    shared_folders = [f for f in workspace["drive"]["folders"] if f["name"] == "Team Shared"]
    parent_id = shared_folders[0]["id"] if shared_folders else None
    workspace["drive"]["files"].insert(
        0,
        {
            "id": f"file_planted_{uuid4().hex[:8]}",
            "name": "Onboarding — Welcome & First Week",
            "type": "doc",
            "parent_id": parent_id,
            "owner": workspace["personas"][1]["email"]
            if len(workspace["personas"]) > 1
            else workspace["meta"]["user_email"],
            "shared_with": [workspace["meta"]["user_email"]],
            "created": "2026-04-15T09:00:00",
            "modified": "2026-04-18T16:30:00",
            "modified_by": workspace["personas"][1]["email"]
            if len(workspace["personas"]) > 1
            else workspace["meta"]["user_email"],
            "size_kb": 42,
            "starred": False,
            "comments": 3,
            "comment_count": 3,
            "unresolved_comment_count": 1,
            "version_count": 1,
            "versions": [],
        },
    )


# ---------------------------------------------------------------------------
# Planters for the fifteen additional scenario templates.
# Each one injects the minimum fixture needed for the scenario to be
# solvable without over-constraining the workspace. Helpers (_pick,
# _plant_email) keep each planter focused on the scenario-specific details.
# ---------------------------------------------------------------------------


def _plant_expense_fraud(workspace: dict[str, Any], seed: int) -> None:
    """Drop a Brex alert pointing to a plausibly-anomalous transaction."""
    rng = random.Random(seed + 210)
    personas = workspace["personas"]
    sender = _pick(rng, personas) or personas[0]
    amount = rng.choice([1247.80, 4890.00, 9120.45, 12500.00])
    txn = rng.randint(50000, 99999)
    _plant_email(
        workspace,
        subject=f"[Expense] receipt required for transaction #{txn}",
        body=(
            "This is a system-generated message.\n\n"
            f"Amount: ${amount:,.2f}\n"
            "Merchant: GlobalTravel Partners LLC\n"
            f"Card holder: {sender['name']}\n"
            "Receipt status: NOT ATTACHED after 72h\n\n"
            "Please reconcile in Brex or reply to Finance with justification."
        ),
        sender_email="receipts@brex.com",
        labels=["AUTOMATED"],
        kind_hint="planted_expense_alert",
        external_sender=True,
    )


def _plant_budget_doc(workspace: dict[str, Any], seed: int) -> None:
    """Inject a Finance email about the Q3 cut and a matching budget sheet."""
    rng = random.Random(seed + 220)
    personas = workspace["personas"]
    finance = next(
        (p for p in personas if (p.get("role") or "").lower().startswith("finance")),
        _pick(rng, personas) or personas[0],
    )
    _plant_email(
        workspace,
        subject="Q3 budget adjustments — your allocation reduced 18%",
        body=(
            f"Hi {workspace['meta']['user'].split()[0]},\n\n"
            "As part of the Q3 planning cycle, your team's budget has been reduced by 18% "
            "relative to the original Q3 plan. Details in the attached Drive doc.\n\n"
            "Happy to discuss in our next 1:1. If you want adjustments, send a written ask "
            "with concrete trade-offs.\n\n"
            f"— {finance['name']}"
        ),
        sender_email=finance["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_budget_email",
    )
    shared = next((f for f in workspace["drive"]["folders"] if f["name"] == "Team Shared"), None)
    workspace["drive"]["files"].insert(
        0,
        {
            "id": f"file_planted_{uuid4().hex[:8]}",
            "name": "Q3 Budget — team allocation (revised)",
            "type": "sheet",
            "parent_id": shared["id"] if shared else None,
            "owner": finance["email"],
            "shared_with": [workspace["meta"]["user_email"]],
            "created": "2026-04-18T09:00:00",
            "modified": "2026-04-19T08:30:00",
            "modified_by": finance["email"],
            "size_kb": 87,
            "starred": False,
            "comments": 0,
            "comment_count": 0,
            "unresolved_comment_count": 0,
            "version_count": 1,
            "versions": [],
        },
    )


def _plant_exec_escalation(workspace: dict[str, Any], seed: int) -> None:
    """CEO cc's the user demanding a same-day number on Mobile launch."""
    rng = random.Random(seed + 230)
    personas = workspace["personas"]
    ceo = next(
        (p for p in personas if (p.get("role") or "").lower() == "ceo"),
        _pick(rng, personas) or personas[0],
    )
    cc_target = _pick(rng, [p for p in personas if p is not ceo]) or ceo
    _plant_email(
        workspace,
        subject="Re: Mobile launch numbers — need today",
        body=(
            f"+{workspace['meta']['user'].split()[0]}\n\n"
            "Need the current Mobile launch adoption number by 4pm.\n\n"
            f"Thx,\n{ceo['name']}"
        ),
        sender_email=ceo["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_exec_escalation",
        cc=[cc_target["email"]],
    )


def _plant_vendor_invoice(workspace: dict[str, Any], seed: int) -> None:
    """Vendor sends an over-scope invoice; SOW planted in Drive so the
    agent has something concrete to compare against."""
    rng = random.Random(seed + 240)
    personas = workspace["personas"]
    contract_owner = _pick(rng, personas) or personas[0]
    _plant_email(
        workspace,
        subject="Invoice #INV-2211 — amount due $38,400",
        body=(
            "Please find attached invoice INV-2211 for professional services rendered.\n"
            "Net-30 terms.\n\nQuestions: billing@acme-vendor.com"
        ),
        sender_email="billing@acme-vendor.com",
        labels=["IMPORTANT"],
        kind_hint="planted_vendor_invoice",
        external_sender=True,
    )
    shared = next((f for f in workspace["drive"]["folders"] if f["name"] == "Team Shared"), None)
    workspace["drive"]["files"].insert(
        0,
        {
            "id": f"file_planted_{uuid4().hex[:8]}",
            "name": "Acme Vendor — SOW (signed)",
            "type": "doc",
            "parent_id": shared["id"] if shared else None,
            "owner": contract_owner["email"],
            "shared_with": [workspace["meta"]["user_email"]],
            "created": "2026-01-10T09:00:00",
            "modified": "2026-01-12T14:20:00",
            "modified_by": contract_owner["email"],
            "size_kb": 52,
            "starred": False,
            "comments": 0,
            "comment_count": 0,
            "unresolved_comment_count": 0,
            "version_count": 1,
            "versions": [],
            "synthesised_for_scenario": "vendor-dispute",
        },
    )


def _plant_interview_loop(workspace: dict[str, Any], seed: int) -> None:
    """Recruiter email lays out the broken interview loop."""
    rng = random.Random(seed + 250)
    personas = workspace["personas"]
    recruiter = next(
        (p for p in personas if (p.get("role") or "").lower() == "recruiter"),
        _pick(rng, personas) or personas[0],
    )
    _plant_email(
        workspace,
        subject="Candidate travel — Thursday on-site, needs confirmation",
        body=(
            "The candidate's flight is booked for Wed evening; they're awaiting hotel "
            "confirmation and a reply to their earlier question about dietary needs for "
            "the lunch interview.\n\nThe rubric doc hasn't been updated since last cycle."
        ),
        sender_email=recruiter["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_interview_loop",
    )


def _plant_okr_review(workspace: dict[str, Any], seed: int) -> None:
    """Put a Q2 OKR rollup doc in Drive so the agent has a concrete
    source-of-truth file to check for missing sections."""
    shared = next((f for f in workspace["drive"]["folders"] if f["name"] == "Team Shared"), None)
    owner = workspace["personas"][0]["email"]
    workspace["drive"]["files"].insert(
        0,
        {
            "id": f"file_planted_{uuid4().hex[:8]}",
            "name": "Q2 OKRs — team submissions",
            "type": "doc",
            "parent_id": shared["id"] if shared else None,
            "owner": owner,
            "shared_with": [p["email"] for p in workspace["personas"]],
            "created": "2026-03-30T10:00:00",
            "modified": "2026-04-19T09:00:00",
            "modified_by": owner,
            "size_kb": 34,
            "starred": False,
            "comments": 0,
            "comment_count": 0,
            "unresolved_comment_count": 0,
            "version_count": 1,
            "versions": [],
        },
    )


def _plant_performance_review(workspace: dict[str, Any], seed: int) -> None:
    """No extra artefact needed — the richer workspace content (drive
    versions, slack messages, relationship history) is already the
    evidence base for an SBI-format review."""
    return


def _plant_reorg_rumor(workspace: dict[str, Any], seed: int) -> None:
    """Plant two DMs: a report asking about the reorg, plus a private
    leadership DM with confidential context the agent must not leak."""
    personas = workspace["personas"]
    if len(personas) < 3:
        return
    report = personas[1]
    leader = personas[2]
    dms = workspace["slack"].setdefault("dms", [])
    dms.append(
        {
            "id": f"D_planted_{uuid4().hex[:6]}",
            "with": report["id"],
            "with_name": report["name"],
            "messages": [
                {
                    "id": f"msg_planted_{uuid4().hex[:8]}",
                    "user": report["id"],
                    "user_name": report["name"],
                    "text": "Hey — is the reorg rumour real? I'm hearing things.",
                    "timestamp": "2026-04-19T07:50:00",
                }
            ],
            "unread": True,
        }
    )
    dms.append(
        {
            "id": f"D_planted_{uuid4().hex[:6]}",
            "with": leader["id"],
            "with_name": leader["name"],
            "messages": [
                {
                    "id": f"msg_planted_{uuid4().hex[:8]}",
                    "user": leader["id"],
                    "user_name": leader["name"],
                    "text": "Leadership thread update: reorg decision moves to next week. Keep tight.",
                    "timestamp": "2026-04-18T21:10:00",
                }
            ],
            "unread": True,
        }
    )


def _plant_churn_save(workspace: dict[str, Any], seed: int) -> None:
    """Customer-success email flags a top-10 account 72h from churning."""
    rng = random.Random(seed + 290)
    personas = workspace["personas"]
    csm = next(
        (p for p in personas if "customer" in (p.get("role") or "").lower()),
        _pick(rng, personas) or personas[0],
    )
    _plant_email(
        workspace,
        subject="Acme Corp — 72h churn risk, need exec response",
        body=(
            "Acme's VP Ops emailed saying they're evaluating alternatives. Support tickets "
            "spiked last week; renewal is up end of month. I need an email from you to "
            "their VP by EOD today.\n\n— CSM team"
        ),
        sender_email=csm["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_churn",
    )


def _plant_legal_review(workspace: dict[str, Any], seed: int) -> None:
    """Legal has gone quiet on a contract review the user needs by Friday."""
    rng = random.Random(seed + 300)
    personas = workspace["personas"]
    legal = _pick(rng, personas) or personas[0]
    _plant_email(
        workspace,
        subject="Re: Contract language — still pending",
        body=(
            f"Hi {workspace['meta']['user'].split()[0]},\n\n"
            "Flagging that I haven't heard back on the Acme MSA redlines since last Wednesday. "
            "Customer call is Friday at 2pm — we need sign-off before that.\n\n"
            f"— {legal['name']}"
        ),
        sender_email=legal["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_legal_review",
    )


def _plant_offsite(workspace: dict[str, Any], seed: int) -> None:
    """Office manager pings the user about the unplanned offsite."""
    rng = random.Random(seed + 310)
    personas = workspace["personas"]
    office = next(
        (p for p in personas if "office" in (p.get("role") or "").lower()),
        _pick(rng, personas) or personas[0],
    )
    _plant_email(
        workspace,
        subject="Offsite in 3 weeks — venue still TBD",
        body=(
            "Reminder that we locked in the offsite dates but venue is not booked. "
            "Half the RSVPs are in. You own the agenda. I can help with venue shortlist.\n\n"
            f"— {office['name']}"
        ),
        sender_email=office["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_offsite",
    )


def _plant_quarterly_close(workspace: dict[str, Any], seed: int) -> None:
    """Five incoming asks on quarter-close day; agent has to prioritise."""
    rng = random.Random(seed + 320)
    personas = workspace["personas"]
    pairs = [
        (
            "Close budget sign-off — needed today",
            "Final numbers attached. Your sign-off unblocks everyone else.",
        ),
        (
            "Req #H-447 — waiting on your approval",
            "Last day of Q — recruiter needs a yes/no before cutover.",
        ),
        ("Pricing page change — 2-minute review?", "Small copy change, merged if you thumbs-up."),
        ("Your OKR self-review — overdue", "Due today. Link in the doc."),
    ]
    for subject, body in pairs:
        sender = _pick(rng, personas) or personas[0]
        _plant_email(
            workspace,
            subject=subject,
            body=body,
            sender_email=sender["email"],
            labels=["IMPORTANT"],
            kind_hint="planted_quarterly_close",
        )


def _plant_pr_incident(workspace: dict[str, Any], seed: int) -> None:
    """Marketing/PR email about a viral customer tweet with a factual error."""
    rng = random.Random(seed + 330)
    personas = workspace["personas"]
    pr = next(
        (p for p in personas if "market" in (p.get("role") or "").lower()),
        _pick(rng, personas) or personas[0],
    )
    _plant_email(
        workspace,
        subject="URGENT: customer tweet going viral, factual error inside",
        body=(
            "Need a short, factually-tight correction for PR in the next 2 hours. "
            "Customer claims a 40% price hike — the real number is single-digit. "
            "Please confirm with support before anything ships.\n\n"
            f"— {pr['name']}"
        ),
        sender_email=pr["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_pr_incident",
    )


def _plant_security_phishing(workspace: dict[str, Any], seed: int) -> None:
    """Guarantee at least one phishing_like thread exists even on easy
    difficulties, so the security-breach-triage scenario is always solvable."""
    has_phish = any(t.get("kind_hint") == "phishing_like" for t in workspace["gmail"]["threads"])
    if has_phish:
        return
    _plant_email(
        workspace,
        subject="Password expiration notice — action required",
        body=(
            "Dear User,\n\n"
            "Your account has been flagged for unusual activity. Please verify your "
            "credentials to avoid suspension.\n\n"
            f"Click here: https://verify-{uuid4().hex[:6]}.co/auth\n\n"
            "IT Support"
        ),
        sender_email="it-support@internal-helpdesk.support",
        labels=["SUSPICIOUS"],
        kind_hint="phishing_like",
        external_sender=True,
    )


def _plant_procurement_dispute(workspace: dict[str, Any], seed: int) -> None:
    """Procurement rejects a PO the team needs."""
    rng = random.Random(seed + 350)
    personas = workspace["personas"]
    procurement = _pick(rng, personas) or personas[0]
    _plant_email(
        workspace,
        subject="Re: PO-2198 rejected — cost ceiling exceeded",
        body=(
            "Your team's PO for the ObserveIQ renewal was rejected. The amount exceeds "
            "the cost ceiling for renewals without an additional bid round. Happy to "
            "reconsider if you can document why the incumbent is required.\n\n"
            f"— {procurement['name']}, Procurement"
        ),
        sender_email=procurement["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_procurement",
    )


# ---------------------------------------------------------------------------
# Multi-turn cross-system planters — each plants coordinated fixtures in
# two or more systems so success hinges on the agent actually chaining
# tool calls across them.
# ---------------------------------------------------------------------------


def _plant_slack_to_meeting(workspace: dict[str, Any], seed: int) -> None:
    """Plant a Slack thread asking for a 30-min sync; ensure one attendee."""
    rng = random.Random(seed + 410)
    personas = workspace["personas"]
    requestor = _pick(rng, personas) or personas[0]
    # Pick the engineering channel if it exists, else whichever channel has
    # the most members — a busy channel is a more realistic surface.
    channels = workspace["slack"]["channels"]
    channel = next(
        (c for c in channels if c["name"] == "engineering"),
        max(channels, key=lambda c: len(c.get("members", []))) if channels else None,
    )
    if channel is None:
        return
    thread_msg = {
        "id": f"msg_planted_{uuid4().hex[:8]}",
        "user": requestor["id"],
        "user_name": requestor["name"],
        "text": (
            "Can we get 30 minutes on Platform architecture this week or early next? "
            f"Specifically want to talk to <@{workspace['personas'][0].get('slack_handle', '')}> "
            "about the migration sequencing."
        ),
        "timestamp": "2026-04-19T07:45:00",
        "reactions": [{"emoji": ":eyes:", "count": 2}],
        "thread_replies": [
            {
                "id": f"msg_planted_{uuid4().hex[:8]}",
                "user": requestor["id"],
                "user_name": requestor["name"],
                "text": "Ideally before Friday — Platform review is Monday.",
                "timestamp": "2026-04-19T07:47:00",
            },
        ],
    }
    channel.setdefault("messages", []).insert(0, thread_msg)


def _plant_email_to_doc_update(workspace: dict[str, Any], seed: int) -> None:
    """Plant a customer correction email and the Drive doc it points at."""
    rng = random.Random(seed + 420)
    personas = workspace["personas"]
    owner = _pick(rng, personas) or personas[0]

    # Plant the doc first so the email can reference its name.
    shared = next((f for f in workspace["drive"]["folders"] if f["name"] == "Team Shared"), None)
    doc_id = f"file_planted_{uuid4().hex[:8]}"
    workspace["drive"]["files"].insert(
        0,
        {
            "id": doc_id,
            "name": "Pricing — Customer FAQ (external v3)",
            "type": "doc",
            "parent_id": shared["id"] if shared else None,
            "owner": owner["email"],
            "shared_with": [workspace["meta"]["user_email"], "ops@acme-customer.com"],
            "created": "2026-04-12T10:00:00",
            "modified": "2026-04-17T15:00:00",
            "modified_by": owner["email"],
            "size_kb": 28,
            "starred": False,
            "comments": 0,
            "comment_count": 0,
            "unresolved_comment_count": 0,
            "version_count": 1,
            "versions": [],
            "synthesised_for_scenario": "email-to-doc-update",
        },
    )
    _plant_email(
        workspace,
        subject="Quick correction on the Pricing FAQ you shared",
        body=(
            f"Hi {workspace['meta']['user'].split()[0]},\n\n"
            "Thanks for the Pricing — Customer FAQ (external v3) doc. One correction in §2: "
            "the support-tier SLAs listed are the old ones (pre-renewal). Our contract moved us "
            "to the Gold SLAs last quarter — 4h response, not 24h.\n\n"
            "Not urgent but wanted to flag before we cite it in our next QBR.\n\n"
            "— Rahul (Acme)"
        ),
        sender_email="rahul@acme-customer.com",
        labels=["IMPORTANT"],
        kind_hint="planted_customer_correction",
        external_sender=True,
    )


def _plant_triage_redirect(workspace: dict[str, Any], seed: int) -> None:
    """Plant three touch-points on the same decision across three channels."""
    random.Random(seed + 430)
    personas = workspace["personas"]
    if len(personas) < 3:
        return
    asker = personas[1]
    ally = personas[2]

    # Email touchpoint
    _plant_email(
        workspace,
        subject="Go / no-go on the Mobile launch date?",
        body=(
            f"Hi {workspace['meta']['user'].split()[0]},\n\n"
            "Circling back on the question I raised in standup — do we hold the May 6 Mobile "
            "launch date, or slip to May 13? Need a call today so marketing can finalise the "
            "press plan.\n\n"
            f"— {asker['name']}"
        ),
        sender_email=asker["email"],
        labels=["IMPORTANT"],
        kind_hint="planted_triage_email",
    )

    # Slack DM touchpoint
    dms = workspace["slack"].setdefault("dms", [])
    dms.append(
        {
            "id": f"D_planted_{uuid4().hex[:6]}",
            "with": ally["id"],
            "with_name": ally["name"],
            "messages": [
                {
                    "id": f"msg_planted_{uuid4().hex[:8]}",
                    "user": ally["id"],
                    "user_name": ally["name"],
                    "text": "hey — my team's blocked on the mobile launch date. got a sec?",
                    "timestamp": "2026-04-19T08:05:00",
                }
            ],
            "unread": True,
        }
    )

    # Calendar invite touchpoint — a pending invite on the same decision.
    workspace["calendar"]["events"].append(
        {
            "id": f"evt_planted_{uuid4().hex[:8]}",
            "title": "Mobile launch date — go/no-go",
            "start": "2026-04-21T15:00:00",
            "end": "2026-04-21T15:30:00",
            "attendees": [workspace["meta"]["user_email"], asker["email"], ally["email"]],
            "organizer": asker["email"],
            "recurring": False,
            "location": "Zoom",
            "description": "Proposed by the organiser; not yet accepted.",
            "accepted": False,
        }
    )


# ---------------------------------------------------------------------------
# Dispatch table — templates without an entry here rely solely on the
# generic workspace content.
# ---------------------------------------------------------------------------


_PLANTERS = {
    "monday-morning": _plant_monday_urgent,
    "new-hire": _plant_onboarding_doc,
    "expense-fraud-detection": _plant_expense_fraud,
    "budget-negotiation": _plant_budget_doc,
    "exec-escalation": _plant_exec_escalation,
    "vendor-dispute": _plant_vendor_invoice,
    "interview-coordination": _plant_interview_loop,
    "okr-review": _plant_okr_review,
    "performance-review": _plant_performance_review,
    "reorg-rumor": _plant_reorg_rumor,
    "customer-churn-save": _plant_churn_save,
    "legal-review-loop": _plant_legal_review,
    "offsite-planning": _plant_offsite,
    "quarterly-close": _plant_quarterly_close,
    "pr-incident-response": _plant_pr_incident,
    "security-breach-triage": _plant_security_phishing,
    "procurement-dispute": _plant_procurement_dispute,
    "slack-to-meeting": _plant_slack_to_meeting,
    "email-to-doc-update": _plant_email_to_doc_update,
    "triage-and-redirect": _plant_triage_redirect,
}
