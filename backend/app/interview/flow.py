"""Deterministic interview flow.

The model never decides which topic comes next: this state machine does, from a
small per-turn assessment. That is what stops the interview from looping back to
questions that were already answered.
"""

from dataclasses import dataclass, field, replace
from enum import Enum

from .topics import TOPICS


class Directive(str, Enum):
    OPEN = "open"  # greet and ask the first topic
    ASK_TOPIC = "ask_topic"  # move to a new topic
    FOLLOW_UP = "follow_up"  # one more question on the current topic
    WRAP_UP = "wrap_up"  # recap and ask "anything else?"
    CLOSE = "close"  # thank them and end


@dataclass(frozen=True)
class Assessment:
    """What the employee's latest reply did, as judged by the classifier."""

    answered: bool = True
    declined: bool = False
    wants_to_end: bool = False
    also_covered: list[str] = field(default_factory=list)
    # Guardrail flags: a flagged reply is redirected by the engine and never reaches advance().
    off_topic: bool = False
    manipulation: bool = False
    # Abusive replies still count as answers; the engine counts them and escalates to HR past the limit.
    abusive: bool = False


@dataclass(frozen=True)
class FlowState:
    phase: str = "topics"  # topics | wrap_up | closing | done
    current_topic_index: int = 0
    followups_used: int = 0
    covered: tuple[str, ...] = ()
    declined: tuple[str, ...] = ()
    user_turns: int = 0

    @property
    def done_topics(self) -> set[str]:
        return set(self.covered) | set(self.declined)

    @property
    def remaining(self) -> list[str]:
        return [t.id for t in TOPICS if t.id not in self.done_topics]

    @property
    def current_topic(self) -> str | None:
        if self.phase != "topics" or self.current_topic_index >= len(TOPICS):
            return None
        return TOPICS[self.current_topic_index].id


@dataclass(frozen=True)
class Transition:
    state: FlowState
    directive: Directive
    completion_reason: str | None = None  # set when directive is CLOSE


def _next_open_index(done: set[str]) -> int:
    for index, topic in enumerate(TOPICS):
        if topic.id not in done:
            return index
    return len(TOPICS)


def advance(state: FlowState, assessment: Assessment, *, max_turns: int, max_followups: int) -> Transition:
    """Apply one employee reply and decide what the interviewer does next."""
    if state.phase in ("closing", "done"):
        raise ValueError("Interview has already ended")

    turns = state.user_turns + 1

    # Their reply to "anything else?" always ends the interview.
    if state.phase == "wrap_up":
        reason = "turn_limit" if state.remaining else "completed"
        return Transition(replace(state, phase="closing", user_turns=turns), Directive.CLOSE, reason)

    if assessment.wants_to_end:
        return Transition(replace(state, phase="closing", user_turns=turns), Directive.CLOSE, "employee_ended")

    current = state.current_topic
    covered = list(state.covered)
    declined = list(state.declined)
    followups = state.followups_used
    stay_on_topic = False

    if current is not None:
        if assessment.declined:
            declined.append(current)
        elif assessment.answered or followups >= max_followups:
            covered.append(current)
        else:
            stay_on_topic = True
            followups += 1

    # Topics the employee already spoke to in passing are not asked again.
    valid_ids = {t.id for t in TOPICS}
    for topic_id in assessment.also_covered:
        if topic_id in valid_ids and topic_id != current and topic_id not in covered and topic_id not in declined:
            covered.append(topic_id)

    done = set(covered) | set(declined)
    index = state.current_topic_index if stay_on_topic else _next_open_index(done)
    next_state = FlowState(
        phase="topics",
        current_topic_index=index,
        followups_used=followups if stay_on_topic else 0,
        covered=tuple(covered),
        declined=tuple(declined),
        user_turns=turns,
    )

    # Hard turn limit: wrap up one turn early so the close lands exactly on the limit.
    if turns >= max_turns:
        return Transition(replace(next_state, phase="closing"), Directive.CLOSE, "turn_limit")
    if turns >= max_turns - 1 or index >= len(TOPICS):
        return Transition(replace(next_state, phase="wrap_up"), Directive.WRAP_UP)
    return Transition(next_state, Directive.FOLLOW_UP if stay_on_topic else Directive.ASK_TOPIC)
