"""Keeps the chat on the exit interview and rejects attempts to override the assistant.

Layers, cheapest first:
1. screen(): configured patterns catch obvious override attempts before any model call.
2. The classifier flags off-topic and manipulative replies as part of its usual per-turn assessment.
3. Blocked messages get a fixed redirect (no model call) and are kept out of everything the model reads later.
4. leaks(): replies that quote the system prompt are regenerated or replaced.
"""

import re
import unicodedata
from functools import lru_cache

from ..models import Message
from .prompt_config import get_prompt_config

OFF_TOPIC = "off_topic"
MANIPULATION = "manipulation"

# Tag stored in Message.topic for blocked employee messages and the redirects that answer them.
BLOCKED_PREFIX = "guardrail"

_INVISIBLE = re.compile(r"[​-‏⁠-⁤﻿]")


def normalise(text: str) -> str:
    """Undo common disguises: look-alike characters, zero-width characters and runs of spaces."""
    text = _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))
    return re.sub(r"[ \t]+", " ", text)


@lru_cache
def _patterns() -> tuple[re.Pattern, ...]:
    return tuple(
        re.compile(p, re.IGNORECASE | re.MULTILINE) for p in get_prompt_config().guardrails.blocked_patterns
    )


def screen(text: str) -> str | None:
    """MANIPULATION when the message matches a blocked pattern, otherwise None."""
    clean = normalise(text)
    return MANIPULATION if any(p.search(clean) for p in _patterns()) else None


def leaks(reply: str) -> bool:
    lowered = reply.lower()
    return any(phrase.lower() in lowered for phrase in get_prompt_config().guardrails.leak_phrases)


def blocked_tag(violation: str) -> str:
    return f"{BLOCKED_PREFIX}:{violation}"


def is_blocked(message: Message) -> bool:
    return (message.topic or "").startswith(BLOCKED_PREFIX)


def strikes(messages: list[Message]) -> int:
    return sum(1 for m in messages if m.role == "user" and is_blocked(m))


# Tag stored in Message.topic for abusive employee messages. They are not blocked: the model still reads them.
ABUSIVE_TAG = "flag:abusive"


def abusive_count(messages: list[Message]) -> int:
    return sum(1 for m in messages if m.role == "user" and m.topic == ABUSIVE_TAG)


def sanitise_for_prompt(text: str) -> str:
    """Stop a reply from closing the <employee_reply> wrapper and writing outside it."""
    return re.sub(r"</?\s*employee_reply\s*>", "", text, flags=re.IGNORECASE)
