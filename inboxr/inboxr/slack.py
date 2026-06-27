"""Slack workspace generation — channels, DMs, mentions, threaded replies."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from inboxr.personas import Persona

DEFAULT_CHANNELS = [
    ("general", "Company-wide announcements", False),
    ("random", "Non-work chatter", False),
    ("engineering", "Eng team", False),
    ("product", "Product discussion", False),
    ("design", "Design team", False),
    ("incidents", "Production incidents", False),
    ("help", "Ask for help", False),
    ("leadership", "Leadership only", True),
]


CHANNEL_MESSAGES = [
    "anyone seeing the 503s?",
    "deploy going out in 10",
    "PR ready for review: {link}",
    "who owns the {project} doc?",
    "welcome {name} 👋",
    "lunch at 12:30?",
    "meeting notes from today: {link}",
    "heads up — calendar invite coming",
    "can someone double-check the numbers on {project}?",
    "customer just reported issue with {project}",
    "rolling back {project} change",
    "on-call this week is {name}",
    "reminder: retros moved to Thursdays",
    "great work everyone on {project} 🎉",
    "quick question — where do we log {thing}?",
    "does anyone have access to {thing}?",
]

DM_MESSAGES = [
    "got a sec?",
    "can i steal you for 10 min?",
    "re: {project} — want to chat?",
    "sent you a doc, let me know",
    "ack'd, will handle",
    "not urgent but when you have time",
    "thanks for the help earlier",
    "heads up, {name} asked me about {project}",
    "fyi {project} slipped to next sprint",
    "you free now?",
    "can we talk about {project}?",
    "i disagree with the direction on {project}, let's discuss",
]


def generate_slack(
    personas: list[Persona],
    seed: int = 42,
    difficulty: str = "medium",
    user_index: int = 0,
) -> dict[str, Any]:
    """Generate a Slack workspace state.

    Returns:
        {"channels": [...], "dms": [...], "mentions": [...]}
    """
    rng = random.Random(seed + 2)
    user = personas[user_index]
    others = [p for i, p in enumerate(personas) if i != user_index]

    msg_counts = {"easy": 20, "medium": 80, "hard": 200, "crisis": 500}
    total_msgs = msg_counts.get(difficulty, 80)

    now = datetime(2026, 4, 19, 8, 0, 0)
    projects = ["Atlas", "Phoenix", "pricing-redesign", "mobile-v2", "onboarding"]

    # Channels
    channels: list[dict[str, Any]] = []
    for ch_name, topic, is_private in DEFAULT_CHANNELS:
        members = [user.id]
        # Most people in most channels
        for p in others:
            if rng.random() < (0.3 if is_private else 0.7):
                members.append(p.id)

        n_msgs = total_msgs // len(DEFAULT_CHANNELS)
        messages = []
        for _ in range(n_msgs):
            sender = rng.choice([personas[0]] + others) if members else rng.choice(others)
            if sender.id not in members:
                continue
            tmpl = rng.choice(CHANNEL_MESSAGES)
            text = tmpl.format(
                project=rng.choice(projects),
                name=rng.choice(others).name.split()[0],
                link=f"https://docs/{uuid4().hex[:8]}",
                thing=rng.choice(
                    ["the staging creds", "the roadmap", "the design file", "the metrics dashboard"]
                ),
            )
            # Sometimes @-mention the user
            if rng.random() < 0.08:
                text = f"<@{user.slack_handle}> {text}"

            t = now - timedelta(hours=rng.randint(0, 96), minutes=rng.randint(0, 59))
            messages.append(
                {
                    "id": f"msg_{uuid4().hex[:10]}",
                    "user": sender.id,
                    "user_name": sender.name,
                    "text": text,
                    "timestamp": t.isoformat(),
                    "reactions": _maybe_reactions(rng),
                    "thread_replies": _maybe_replies(rng, others, projects, t),
                }
            )

        messages.sort(key=lambda m: m["timestamp"])
        channels.append(
            {
                "id": f"C_{uuid4().hex[:8]}",
                "name": ch_name,
                "topic": topic,
                "is_private": is_private,
                "members": members,
                "messages": messages,
                "unread_count": sum(1 for m in messages if rng.random() < 0.3),
            }
        )

    # DMs
    dms: list[dict[str, Any]] = []
    n_dms = rng.randint(3, min(8, len(others)))
    for other in rng.sample(others, n_dms):
        n_dm_msgs = rng.randint(2, 15)
        dm_messages = []
        t = now - timedelta(hours=rng.randint(0, 48))
        for i in range(n_dm_msgs):
            sender = other if i % 2 == 0 else user
            tmpl = rng.choice(DM_MESSAGES)
            text = tmpl.format(
                project=rng.choice(projects),
                name=rng.choice(others).name.split()[0],
            )
            dm_messages.append(
                {
                    "id": f"msg_{uuid4().hex[:10]}",
                    "user": sender.id,
                    "user_name": sender.name,
                    "text": text,
                    "timestamp": t.isoformat(),
                }
            )
            t += timedelta(minutes=rng.randint(1, 240))

        dms.append(
            {
                "id": f"D_{uuid4().hex[:8]}",
                "with": other.id,
                "with_name": other.name,
                "messages": dm_messages,
                "unread": rng.random() < 0.4,
            }
        )

    # Mentions — flattened list of places the user was tagged
    mentions = []
    for ch in channels:
        for m in ch["messages"]:
            if user.slack_handle in m["text"]:
                mentions.append(
                    {
                        "channel": ch["name"],
                        "message_id": m["id"],
                        "from": m["user_name"],
                        "text": m["text"],
                        "timestamp": m["timestamp"],
                    }
                )

    return {
        "user": user.id,
        "channels": channels,
        "dms": dms,
        "mentions": sorted(mentions, key=lambda m: m["timestamp"], reverse=True),
        "summary": {
            "total_channels": len(channels),
            "total_dms": len(dms),
            "total_mentions": len(mentions),
            "difficulty": difficulty,
        },
    }


def _maybe_reactions(rng: random.Random) -> list[dict[str, Any]]:
    if rng.random() > 0.3:
        return []
    emojis = rng.sample(
        [":+1:", ":eyes:", ":fire:", ":heart:", ":tada:", ":thinking:"], k=rng.randint(1, 2)
    )
    return [{"emoji": e, "count": rng.randint(1, 5)} for e in emojis]


def _maybe_replies(
    rng: random.Random, others: list[Persona], projects: list[str], parent_time: datetime
) -> list[dict]:
    if rng.random() > 0.2:
        return []
    n = rng.randint(1, 4)
    replies = []
    t = parent_time
    for _ in range(n):
        sender = rng.choice(others)
        t += timedelta(minutes=rng.randint(1, 30))
        replies.append(
            {
                "id": f"msg_{uuid4().hex[:10]}",
                "user": sender.id,
                "user_name": sender.name,
                "text": rng.choice(
                    [
                        "+1",
                        "ack",
                        "will look",
                        "same",
                        "on it",
                        f"yeah {rng.choice(projects)} is a mess",
                    ]
                ),
                "timestamp": t.isoformat(),
            }
        )
    return replies
