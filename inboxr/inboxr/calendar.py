"""Calendar generation — meetings, conflicts, recurring events, focus blocks."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from inboxr.personas import Persona

MEETING_TYPES = [
    ("1:1 with {name}", 30, False),
    ("Weekly team sync", 60, True),
    ("{project} standup", 15, True),
    ("{project} kickoff", 60, False),
    ("{project} review", 45, False),
    ("Interview: {name}", 60, False),
    ("All-hands", 60, True),
    ("Design critique", 45, True),
    ("Customer call: {name}", 30, False),
    ("Roadmap planning", 90, False),
    ("Offsite prep", 60, False),
    ("Board prep", 120, False),
    ("Focus time", 120, False),
    ("Lunch with {name}", 60, False),
]


def generate_calendar(
    personas: list[Persona],
    seed: int = 42,
    difficulty: str = "medium",
    user_index: int = 0,
    days: int = 7,
) -> dict[str, Any]:
    """Generate a calendar for the user with realistic conflicts and patterns.

    Args:
        days: number of days to generate (starting today)
    """
    rng = random.Random(seed + 3)
    user = personas[user_index]
    others = [p for i, p in enumerate(personas) if i != user_index]

    meeting_counts = {"easy": 3, "medium": 8, "hard": 15, "crisis": 25}
    meetings_per_day = meeting_counts.get(difficulty, 8) // 3

    projects = ["Atlas", "Phoenix", "Q2 planning", "Mobile launch", "Customer Summit"]
    start_date = datetime(2026, 4, 19, 0, 0, 0)

    events: list[dict[str, Any]] = []
    for day_offset in range(days):
        day = start_date + timedelta(days=day_offset)
        # Skip weekends in easy, partial in others
        is_weekend = day.weekday() >= 5
        if is_weekend and difficulty in ("easy", "medium"):
            continue
        if is_weekend and rng.random() > 0.3:
            continue

        # Generate meetings for this day
        n = meetings_per_day + rng.randint(-1, 2)
        if difficulty == "crisis":
            n += rng.randint(2, 5)

        for _ in range(max(0, n)):
            m_tmpl, duration, is_recurring = rng.choice(MEETING_TYPES)
            other = rng.choice(others)
            title = m_tmpl.format(
                name=other.name.split()[0],
                project=rng.choice(projects),
            )

            # Hour: weighted toward 9-5 with some chaos in crisis
            if difficulty == "crisis":
                start_hour = rng.randint(7, 19)
            else:
                start_hour = rng.choices(
                    range(8, 19), weights=[1, 3, 4, 5, 4, 2, 4, 5, 4, 3, 1], k=1
                )[0]
            start_minute = rng.choice([0, 0, 0, 15, 30, 30, 45])

            start = day.replace(hour=start_hour, minute=start_minute)
            end = start + timedelta(minutes=duration)

            attendees = [user.email, other.email]
            # Larger meetings pull in more people
            if duration >= 45:
                extras = rng.sample(others, min(rng.randint(1, 4), len(others)))
                attendees.extend([p.email for p in extras if p.email not in attendees])

            events.append(
                {
                    "id": f"evt_{uuid4().hex[:10]}",
                    "title": title,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "attendees": list(set(attendees)),
                    "organizer": other.email if "with" in title or "1:1" in title else user.email,
                    "recurring": is_recurring,
                    "location": rng.choice(
                        ["Zoom", "Meet", "Conference Room A", "Conference Room B", "Cafe"]
                    ),
                    "description": _describe(title, rng),
                    "accepted": rng.random() < 0.8,
                }
            )

    # Sort events
    events.sort(key=lambda e: e["start"])

    # Detect conflicts
    conflicts = []
    for i, e1 in enumerate(events):
        for e2 in events[i + 1 :]:
            if e2["start"] >= e1["end"]:
                break
            if e1["start"] < e2["end"] and e2["start"] < e1["end"]:
                conflicts.append({"event_a": e1["id"], "event_b": e2["id"]})

    return {
        "user": user.email,
        "timezone": user.timezone,
        "working_hours": list(user.working_hours),
        "events": events,
        "conflicts": conflicts,
        "summary": {
            "total_events": len(events),
            "conflict_count": len(conflicts),
            "days_covered": days,
            "difficulty": difficulty,
        },
    }


def _describe(title: str, rng: random.Random) -> str:
    if "1:1" in title:
        return "Regular 1:1 — bring anything on your mind."
    if "standup" in title.lower():
        return "Daily standup. 3 questions: yesterday / today / blockers."
    if "review" in title.lower():
        return "Review progress, surface blockers, agree on next steps."
    if "interview" in title.lower():
        return "Candidate interview. See attached resume and rubric."
    if "focus" in title.lower():
        return "Deep work block — no meetings please."
    return rng.choice(
        ["Agenda in the invite.", "See shared doc.", "", "Dial-in details in description."]
    )
