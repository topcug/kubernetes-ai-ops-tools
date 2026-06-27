"""WhatsApp generation — personal chats, group threads, media references.

Personal messaging is the cross-boundary layer in a scenario: work leaks
into it (a client texting the user directly) and personal life competes
with work urgency (your mom's appointment the same day as a crisis
meeting). This module now models:

- **Typed contacts** with a contact_type (family, friend, partner, service,
  work_personal) so downstream scenarios can reason about who is who.
- **Topic-aware conversations** — messages inside one chat cluster around a
  coherent topic (logistics, planning, small talk, emergency) rather than
  being drawn uniformly from a flat pool.
- **Media references** — photos, voice notes, videos, documents, shared
  locations, all as first-class payloads with filenames, durations and
  captions where appropriate.
- **Reply-to / quoting** — a share of messages explicitly reply to an
  earlier one, which matters for Q&A-style group chats.
- **Read receipts and delivery state** — each message carries `delivered`
  and `read` booleans so agents can surface "unread from your wife".
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from inboxr.personas import Persona

# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


# Each entry: (display_name, contact_type, relationship_weight)
# relationship_weight biases how often this contact appears and how
# high-priority unread messages from them feel.
PERSONAL_CONTACTS = [
    ("Mom", "family", 0.95),
    ("Dad", "family", 0.85),
    ("Partner", "partner", 0.99),
    ("Sister", "family", 0.75),
    ("Brother", "family", 0.70),
    ("Best Friend", "friend", 0.80),
    ("Alex", "friend", 0.55),
    ("Sam", "friend", 0.55),
    ("Jordan", "friend", 0.50),
    ("Taylor", "friend", 0.50),
    ("Neighbor", "friend", 0.40),
    ("Landlord", "service", 0.35),
    ("Plumber", "service", 0.20),
    ("Doctor's Office", "service", 0.30),
    ("Dentist", "service", 0.25),
    ("Cleaner", "service", 0.25),
    ("Daycare", "service", 0.60),
    ("Babysitter", "service", 0.55),
    ("Personal Trainer", "service", 0.40),
    ("Barber", "service", 0.15),
]


# ---------------------------------------------------------------------------
# Topic catalogue — each topic is a small pool of templates that cluster
# coherently if picked in sequence. The generator samples one topic per chat
# "turn" and draws a few messages from it.
# ---------------------------------------------------------------------------


CHAT_TOPICS = {
    # (topic_name, relevant_contact_types): [templates]
    "logistics": {
        "targets": {"family", "partner", "friend", "service"},
        "lines": [
            "what time?",
            "running {mins} min late",
            "omw",
            "be there in 10",
            "can we push to {time}?",
            "tomorrow still good?",
            "moved to {day}?",
            "address again?",
            "need me to bring anything?",
            "parking nightmare — start without me",
        ],
    },
    "planning": {
        "targets": {"family", "partner", "friend"},
        "lines": [
            "dinner {day}?",
            "thinking Italian, you in?",
            "booked the table for {time}",
            "can we do breakfast instead?",
            "long weekend — should we go somewhere?",
            "my calendar is nuts this week",
            "tuesday or thursday works",
            "kids can come too if that's easier",
            "should we split the bill this time",
            "tickets released at 10 — setting an alarm",
        ],
    },
    "small_talk": {
        "targets": {"family", "partner", "friend"},
        "lines": [
            "haha",
            "true",
            "omg that's so you",
            "miss you",
            "saw this and thought of you [photo]",
            "lol",
            "🙃",
            "ok sounds good",
            "how was today?",
            "proud of you",
            "thanks!!",
        ],
    },
    "family_emergency": {
        "targets": {"family", "partner"},
        "lines": [
            "can you call when you can",
            "it's about {topic}",
            "not urgent-urgent but today",
            "don't want to do this over text",
            "spoke to the doctor",
            "hospital visit went ok",
            "she's home now, resting",
            "we'll figure it out",
        ],
    },
    "service_scheduling": {
        "targets": {"service"},
        "lines": [
            "confirming your appointment {date} at {time}",
            "reply YES to confirm, CANCEL to reschedule",
            "can we reschedule to {day}?",
            "running 15 min behind, sorry",
            "invoice attached",
            "estimated arrival {time}",
            "payment received, thanks",
            "appointment confirmed",
        ],
    },
    "shopping_run": {
        "targets": {"family", "partner"},
        "lines": [
            "can you grab milk?",
            "we're out of coffee",
            "add bread to the list",
            "they were out of {item} — got {item2} instead",
            "paying, be home in 20",
            "forgot cash — can you venmo me",
            "the oat milk or the 2%?",
        ],
    },
    "care_logistics": {
        "targets": {"service", "family", "partner"},
        "lines": [
            "pickup at 5 today?",
            "she was a bit sniffly this morning, keep an eye",
            "school called — nothing bad, just a reminder",
            "form needs signing, dropped in backpack",
            "he ate all his lunch 🎉",
            "nap was short, he might be tired tonight",
            "report card attached",
        ],
    },
}


# Group chat definitions. Each group has a name, a typed member list, and a
# set of topics it tends to lean on.
GROUP_CHATS = [
    {
        "name": "Family",
        "members": ["mom", "dad", "sister", "brother"],
        "topics": ["small_talk", "family_emergency", "planning", "logistics"],
    },
    {
        "name": "College friends",
        "members": ["alex", "sam", "jordan", "taylor", "riley"],
        "topics": ["small_talk", "planning", "logistics"],
    },
    {
        "name": "Book club",
        "members": ["mia", "chris", "pat", "dev"],
        "topics": ["planning", "small_talk"],
    },
    {
        "name": "Apartment",
        "members": ["landlord", "roommate"],
        "topics": ["logistics", "service_scheduling"],
    },
    {
        "name": "Running group",
        "members": ["coach", "amy", "ben"],
        "topics": ["planning", "logistics", "small_talk"],
    },
    {
        "name": "School parents",
        "members": ["miriam", "jacob", "hanna", "alex"],
        "topics": ["care_logistics", "logistics", "small_talk"],
    },
]


# Media attachment prototypes. Chosen by topic.
MEDIA_LIBRARY = {
    "photo": [
        {"filename": "IMG_{n}.jpg", "caption": "look at this"},
        {"filename": "IMG_{n}.jpg", "caption": "today's sky"},
        {"filename": "IMG_{n}.jpg", "caption": "kids at the park"},
        {"filename": "IMG_{n}.jpg", "caption": "dinner we made"},
        {"filename": "IMG_{n}.jpg", "caption": None},
    ],
    "video": [
        {"filename": "VID_{n}.mp4", "duration_seconds": 14, "caption": "he said his first word"},
        {"filename": "VID_{n}.mp4", "duration_seconds": 22, "caption": "watch this"},
    ],
    "voice_note": [
        {"filename": "PTT_{n}.ogg", "duration_seconds": 7, "caption": None},
        {"filename": "PTT_{n}.ogg", "duration_seconds": 21, "caption": None},
        {"filename": "PTT_{n}.ogg", "duration_seconds": 48, "caption": None},
    ],
    "document": [
        {"filename": "invoice_{n}.pdf", "caption": "invoice"},
        {"filename": "report_{n}.pdf", "caption": "report card"},
        {"filename": "estimate_{n}.pdf", "caption": "quote from the plumber"},
    ],
    "location": [
        {"place": "The restaurant", "lat": 37.7749, "lon": -122.4194, "caption": None},
        {"place": "Doctor's office", "lat": 37.7849, "lon": -122.4094, "caption": None},
        {"place": "School", "lat": 37.7649, "lon": -122.4294, "caption": None},
    ],
}


EMERGENCY_TOPICS_WORDS = [
    "mom",
    "dad",
    "the insurance",
    "the school",
    "the test results",
    "the car",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_whatsapp(
    personas: list[Persona],
    seed: int = 42,
    difficulty: str = "medium",
    user_index: int = 0,
) -> dict[str, Any]:
    """Generate a WhatsApp state with personal and group chats.

    WhatsApp contacts are *outside* the work org — family, friends, service
    providers, the occasional work-personal leak.
    """
    rng = random.Random(seed + 5)
    user = personas[user_index]

    chat_counts = {"easy": 3, "medium": 8, "hard": 15, "crisis": 20}
    n_personal = chat_counts.get(difficulty, 8)

    now = datetime(2026, 4, 19, 8, 0, 0)

    # Select contacts weighted by relationship_weight so partners/family
    # dominate, services come and go, strangers never show up.
    weights = [w for _, _, w in PERSONAL_CONTACTS]
    chosen_indices = _weighted_sample_indices(
        n=min(n_personal, len(PERSONAL_CONTACTS)),
        weights=weights,
        rng=rng,
    )
    chosen = [PERSONAL_CONTACTS[i] for i in chosen_indices]

    chats: list[dict[str, Any]] = []

    # Personal 1:1 chats
    for display_name, contact_type, rel_weight in chosen:
        chat = _generate_personal_chat(
            display_name=display_name,
            contact_type=contact_type,
            rel_weight=rel_weight,
            user=user,
            now=now,
            difficulty=difficulty,
            rng=rng,
        )
        chats.append(chat)

    # Groups — count scales with difficulty
    n_groups = {"easy": 1, "medium": 2, "hard": 3, "crisis": 4}.get(difficulty, 2)
    for group_def in rng.sample(GROUP_CHATS, min(n_groups, len(GROUP_CHATS))):
        chats.append(
            _generate_group_chat(
                group_def=group_def,
                user=user,
                now=now,
                difficulty=difficulty,
                rng=rng,
            )
        )

    total_messages = sum(len(c["messages"]) for c in chats)
    total_media = sum(1 for c in chats for m in c["messages"] if m.get("media") is not None)
    total_unread = sum(c["unread"] for c in chats)

    return {
        "user": "user",
        "chats": chats,
        "summary": {
            "total_chats": len(chats),
            "total_messages": total_messages,
            "media_messages": total_media,
            "unread_messages": total_unread,
            "difficulty": difficulty,
        },
    }


# ---------------------------------------------------------------------------
# Personal 1:1
# ---------------------------------------------------------------------------


def _generate_personal_chat(
    display_name: str,
    contact_type: str,
    rel_weight: float,
    user: Persona,
    now: datetime,
    difficulty: str,
    rng: random.Random,
) -> dict[str, Any]:
    # Close family/partners have more messages and recent activity
    base_msgs = {"easy": 6, "medium": 12, "hard": 22, "crisis": 30}[difficulty]
    n_msgs = max(2, int(base_msgs * (0.6 + rel_weight * 0.8)))
    contact_handle = _handle(display_name)

    # Pick a topic pool appropriate to this contact type. For partners we
    # may also sprinkle in an emergency thread at crisis difficulty.
    topic_pool = [name for name, t in CHAT_TOPICS.items() if contact_type in t["targets"]]
    if not topic_pool:
        topic_pool = ["small_talk"]

    # Start timestamp — more important relationships skew more recent.
    t = now - timedelta(hours=rng.uniform(0, 48 * (1.2 - rel_weight)))

    messages: list[dict[str, Any]] = []
    while len(messages) < n_msgs:
        # One conversational "beat" ~ 2-5 messages from one topic
        topic = rng.choice(topic_pool)
        if difficulty == "crisis" and contact_type in ("family", "partner") and rng.random() < 0.25:
            topic = "family_emergency"

        beat_len = rng.randint(2, 5)
        for i in range(beat_len):
            if len(messages) >= n_msgs:
                break
            is_user = (i % 2 == 1) if rng.random() < 0.7 else rng.random() < 0.4
            sender_key = "user" if is_user else contact_handle
            sender_name = user.name if is_user else display_name

            text = _render_topic_line(topic, contact_type, rng)
            media = _maybe_media(topic, rng)
            reply_to = _maybe_reply_to(messages, rng)

            msg = {
                "id": f"wa_{uuid4().hex[:10]}",
                "from": sender_key,
                "from_name": sender_name,
                "text": text,
                "timestamp": t.isoformat(),
                "delivered": True,
                "read": rng.random() < 0.7,
                "topic": topic,
            }
            if media is not None:
                msg["media"] = media
            if reply_to is not None:
                msg["reply_to"] = reply_to

            messages.append(msg)
            t += timedelta(minutes=rng.randint(1, 180))

    return {
        "id": f"chat_{uuid4().hex[:8]}",
        "type": "personal",
        "name": display_name,
        "contact_type": contact_type,
        "contact_handle": contact_handle,
        "relationship_weight": round(rel_weight, 2),
        "messages": messages,
        "unread": sum(1 for m in messages if not m["read"] and m["from"] != "user"),
        "pinned": contact_type in ("partner", "family") and rng.random() < 0.5,
        "muted": rng.random() < 0.1,
    }


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def _generate_group_chat(
    group_def: dict[str, Any],
    user: Persona,
    now: datetime,
    difficulty: str,
    rng: random.Random,
) -> dict[str, Any]:
    base_msgs = {"easy": 8, "medium": 18, "hard": 35, "crisis": 60}[difficulty]
    n_msgs = base_msgs + rng.randint(-4, 8)
    n_msgs = max(5, n_msgs)

    members = group_def["members"]
    topic_pool = group_def["topics"]

    t = now - timedelta(hours=rng.uniform(0, 72))
    messages: list[dict[str, Any]] = []

    while len(messages) < n_msgs:
        topic = rng.choice(topic_pool)
        beat_len = rng.randint(2, 6)
        for i in range(beat_len):
            if len(messages) >= n_msgs:
                break
            # In groups the sender is any member including the user.
            sender_key = rng.choice(members + ["user"])
            sender_name = user.name if sender_key == "user" else sender_key.title()

            text = _render_topic_line(topic, "friend", rng)
            media = _maybe_media(topic, rng)
            reply_to = _maybe_reply_to(messages, rng, probability=0.25)

            msg = {
                "id": f"wa_{uuid4().hex[:10]}",
                "from": sender_key,
                "from_name": sender_name,
                "text": text,
                "timestamp": t.isoformat(),
                "delivered": True,
                "read": rng.random() < 0.6,
                "topic": topic,
            }
            if media is not None:
                msg["media"] = media
            if reply_to is not None:
                msg["reply_to"] = reply_to

            messages.append(msg)
            t += timedelta(minutes=rng.randint(1, 120))

    return {
        "id": f"chat_{uuid4().hex[:8]}",
        "type": "group",
        "name": group_def["name"],
        "members": members,
        "topics": topic_pool,
        "messages": messages,
        "unread": sum(1 for m in messages if not m["read"] and m["from"] != "user"),
        "pinned": rng.random() < 0.3,
        "muted": rng.random() < 0.2,
    }


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_topic_line(topic: str, contact_type: str, rng: random.Random) -> str:
    tmpl = rng.choice(CHAT_TOPICS.get(topic, CHAT_TOPICS["small_talk"])["lines"])
    return tmpl.format(
        time=rng.choice(["7pm", "6:30", "8:15", "11am", "4pm"]),
        day=rng.choice(["Monday", "Tuesday", "Saturday", "tomorrow", "Friday"]),
        date=rng.choice(["Apr 22", "Apr 24", "next Tuesday", "the 30th"]),
        mins=rng.choice([5, 10, 15, 20]),
        item=rng.choice(["eggs", "oat milk", "rye bread", "tomatoes"]),
        item2=rng.choice(["almond milk", "sourdough", "romas", "whatever they had"]),
        topic=rng.choice(EMERGENCY_TOPICS_WORDS),
    )


def _maybe_media(topic: str, rng: random.Random) -> dict[str, Any] | None:
    """Attach a media payload some of the time.

    Photos are the most common; documents cluster with service topics;
    locations cluster with logistics.
    """
    if rng.random() > 0.18:
        return None

    if topic == "service_scheduling":
        kind = rng.choices(["document", "photo"], weights=[3, 1], k=1)[0]
    elif topic == "logistics":
        kind = rng.choices(["location", "photo", "voice_note"], weights=[2, 2, 1], k=1)[0]
    elif topic in ("family_emergency",):
        kind = rng.choices(["voice_note", "photo"], weights=[2, 1], k=1)[0]
    else:
        kind = rng.choices(
            ["photo", "video", "voice_note", "location", "document"],
            weights=[6, 1, 2, 1, 1],
            k=1,
        )[0]

    proto = dict(rng.choice(MEDIA_LIBRARY[kind]))
    proto["kind"] = kind
    if "filename" in proto:
        proto["filename"] = proto["filename"].format(n=rng.randint(1000, 9999))
    return proto


def _maybe_reply_to(
    messages: list[dict[str, Any]],
    rng: random.Random,
    probability: float = 0.15,
) -> dict[str, str] | None:
    """Occasionally mark a message as an explicit reply to a recent one."""
    if not messages or rng.random() > probability:
        return None
    target = rng.choice(messages[-min(len(messages), 6) :])
    snippet = (target["text"] or "").strip()
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."
    return {"message_id": target["id"], "snippet": snippet}


def _handle(display_name: str) -> str:
    return display_name.lower().replace(" ", "_").replace("'", "")


def _weighted_sample_indices(n: int, weights: list[float], rng: random.Random) -> list[int]:
    """Sample n distinct indices without replacement, weighted."""
    pool = list(range(len(weights)))
    chosen: list[int] = []
    local_weights = list(weights)
    for _ in range(n):
        total = sum(local_weights[i] for i in pool)
        if total <= 0 or not pool:
            break
        r = rng.uniform(0, total)
        acc = 0.0
        for idx_in_pool, i in enumerate(pool):
            acc += local_weights[i]
            if acc >= r:
                chosen.append(i)
                pool.pop(idx_in_pool)
                break
    return chosen
