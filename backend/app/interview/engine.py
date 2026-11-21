import logging
import re
from dataclasses import replace
from difflib import SequenceMatcher

from ..config import Settings
from ..llm.base import ChatMessage, LLMError, LLMProvider, parse_json_object
from ..models import Interview, Message, utcnow
from .flow import Assessment, Directive, FlowState, Transition, advance
from .guardrails import (
    ABUSIVE_TAG,
    MANIPULATION,
    OFF_TOPIC,
    abusive_count,
    blocked_tag,
    is_blocked,
    leaks,
    screen,
    strikes,
)
from .prompt_config import get_prompt_config
from .prompts import (
    COMPLETION_MARKER,
    classifier_system_prompt,
    classifier_user_prompt,
    first_name,
    interviewer_system_prompt,
    kickoff_message,
    leak_correction,
    repeat_correction,
)
from .topics import TOPIC_BY_ID, TOPICS

log = logging.getLogger(__name__)

REPEAT_SIMILARITY = 0.85


def load_state(interview: Interview) -> FlowState:
    return FlowState(
        phase=interview.phase,
        current_topic_index=interview.current_topic_index,
        followups_used=interview.followups_used,
        covered=tuple(interview.covered_topics or ()),
        declined=tuple(interview.declined_topics or ()),
        user_turns=interview.user_turns,
    )


def save_state(interview: Interview, state: FlowState) -> None:
    interview.phase = state.phase
    interview.current_topic_index = state.current_topic_index
    interview.followups_used = state.followups_used
    # Assign new lists so the JSON columns are flagged as changed.
    interview.covered_topics = list(state.covered)
    interview.declined_topics = list(state.declined)
    interview.user_turns = state.user_turns


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _last_question(text: str) -> str:
    """The question sentence of an assistant message, which is what a loop would repeat."""
    questions = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip().endswith("?")]
    return questions[-1] if questions else text


def is_repeat(candidate: str, previous: list[str]) -> bool:
    new_q = _normalise(_last_question(candidate))
    if not new_q:
        return False
    return any(
        SequenceMatcher(None, new_q, _normalise(_last_question(p))).ratio() >= REPEAT_SIMILARITY for p in previous
    )


def strip_marker(text: str) -> tuple[str, bool]:
    found = COMPLETION_MARKER in text
    return text.replace(COMPLETION_MARKER, "").strip(), found


class InterviewEngine:
    def __init__(self, llm: LLMProvider, settings: Settings):
        self.llm = llm
        self.settings = settings

    # Public operations. The caller commits the session.

    def start(self, interview: Interview) -> Message:
        if interview.status != "pending":
            raise ValueError("Interview already started")
        interview.status = "in_progress"
        interview.started_at = utcnow()
        state = FlowState()
        save_state(interview, state)
        interview.messages.append(Message(role="user", content=kickoff_message(), hidden=True))
        return self._reply(interview, state, Directive.OPEN)

    def respond(self, interview: Interview, text: str) -> Message:
        if interview.status != "in_progress":
            raise ValueError("Interview is not in progress")
        state = load_state(interview)
        question = self._last_assistant_text(interview)

        # Guardrails: obvious override attempts are caught without a model call; the classifier
        # flags subtler off-topic or manipulative replies as part of its usual assessment.
        violation = screen(text)
        assessment = Assessment()
        if violation is None and state.phase in ("topics", "wrap_up"):
            assessment = self._assess(interview, state, question, text)
            violation = MANIPULATION if assessment.manipulation else OFF_TOPIC if assessment.off_topic else None
        if violation:
            return self._block(interview, text, violation, question)

        interview.messages.append(Message(role="user", content=text, topic=ABUSIVE_TAG if assessment.abusive else None))
        if assessment.abusive:
            log.warning("Abusive message in interview %s", interview.id)
            if abusive_count(interview.messages) > get_prompt_config().guardrails.max_abusive_messages:
                return self._escalate(interview, state)

        transition = advance(
            state,
            assessment,
            max_turns=self.settings.max_user_turns,
            max_followups=self.settings.max_followups_per_topic,
        )
        save_state(interview, transition.state)
        return self._reply(interview, transition.state, transition.directive, transition)

    @staticmethod
    def end_early(interview: Interview) -> None:
        """Employee pressed 'End interview' before the flow finished."""
        if interview.status != "in_progress":
            raise ValueError("Interview is not in progress")
        save_state(interview, replace(load_state(interview), phase="done"))
        InterviewEngine._mark_completed(interview, "ended_early")

    # Internals

    def _block(self, interview: Interview, text: str, violation: str, question: str) -> Message:
        """Answer a blocked message with a fixed redirect; end the interview after too many."""
        rules = get_prompt_config().guardrails
        interview.messages.append(Message(role="user", content=text, topic=blocked_tag(violation)))
        log.warning("Guardrail blocked a message (%s) in interview %s", violation, interview.id)
        name = first_name(interview.employee_name)
        company = self.settings.company_name

        if strikes(interview.messages) >= rules.max_strikes:
            content = rules.end_message.strip().format(first_name=name, company=company)
            message = Message(role="assistant", content=content, topic=blocked_tag("end"))
            interview.messages.append(message)
            save_state(interview, replace(load_state(interview), phase="done"))
            self._mark_completed(interview, "guardrail_ended")
            return message

        template = rules.redirect_manipulation if violation == MANIPULATION else rules.redirect_off_topic
        content = template.strip().format(first_name=name, company=company, question=_last_question(question))
        message = Message(role="assistant", content=content, topic=blocked_tag("redirect"))
        interview.messages.append(message)
        return message

    def _escalate(self, interview: Interview, state: FlowState) -> Message:
        """End with a fixed message promising HR follow-up; the router emails the HR executive."""
        rules = get_prompt_config().guardrails
        content = rules.escalation_message.strip().format(
            first_name=first_name(interview.employee_name), company=self.settings.company_name
        )
        message = Message(role="assistant", content=content, topic="escalated")
        interview.messages.append(message)
        save_state(interview, replace(state, phase="done", user_turns=state.user_turns + 1))
        self._mark_completed(interview, "escalated_to_hr")
        return message

    def _assess(self, interview: Interview, state: FlowState, question: str, answer: str) -> Assessment:
        if state.phase == "wrap_up":
            topic_title, topic_id = "Closing: anything else they want to add", "wrap_up"
        else:
            topic = TOPIC_BY_ID[state.current_topic] if state.current_topic else TOPICS[0]
            topic_title, topic_id = topic.title, topic.id
        prompt = classifier_user_prompt(topic_title=topic_title, topic_id=topic_id, question=question, answer=answer)
        try:
            raw = self.llm.complete(
                interview.model,
                classifier_system_prompt(),
                [ChatMessage("user", prompt)],
                json_mode=True,
                temperature=0.0,
            )
            data = parse_json_object(raw)
        except LLMError as exc:
            # Failing open means moving on, which can never cause a loop.
            log.warning("Classifier failed for interview %s: %s", interview.id, exc)
            return Assessment()
        also = data.get("also_covered") or []
        return Assessment(
            answered=bool(data.get("answered", True)),
            declined=bool(data.get("declined", False)),
            wants_to_end=bool(data.get("wants_to_end", False)),
            also_covered=[t for t in also if isinstance(t, str)] if isinstance(also, list) else [],
            off_topic=bool(data.get("off_topic", False)),
            manipulation=bool(data.get("manipulation", False)),
            abusive=bool(data.get("abusive", False)),
        )

    def _reply(
        self, interview: Interview, state: FlowState, directive: Directive, transition: Transition | None = None
    ) -> Message:
        system = interviewer_system_prompt(
            name=interview.employee_name,
            department=interview.department,
            company=self.settings.company_name,
            state=state,
            directive=directive,
        )
        # The full transcript comes from the database every turn, so the model's memory always
        # matches what the employee sees, across refreshes, restarts and server instances.
        # Blocked messages and their redirects are left out, so the model never reads them.
        history = [ChatMessage(m.role, m.content) for m in interview.messages if not is_blocked(m)]
        text, _ = strip_marker(self.llm.complete(interview.model, system, history))

        previous = [m.content for m in interview.messages if m.role == "assistant" and not is_blocked(m)]
        if directive in (Directive.ASK_TOPIC, Directive.FOLLOW_UP) and is_repeat(text, previous):
            log.info("Regenerating repeated question for interview %s", interview.id)
            text, _ = strip_marker(self.llm.complete(interview.model, system + repeat_correction(), history))

        if leaks(text):
            log.warning("Regenerating a reply that quoted its instructions in interview %s", interview.id)
            text, _ = strip_marker(self.llm.complete(interview.model, system + leak_correction(), history))
            if leaks(text):
                text = self._fallback(interview, state, directive)

        tag = state.current_topic if directive in (Directive.OPEN, Directive.ASK_TOPIC, Directive.FOLLOW_UP) else directive.value
        message = Message(role="assistant", content=text, topic=tag)
        interview.messages.append(message)

        # The code decides when the interview ends; a marker emitted at any other point is ignored.
        if directive is Directive.CLOSE:
            interview.phase = "done"
            self._mark_completed(interview, transition.completion_reason if transition else "completed")
        return message

    def _fallback(self, interview: Interview, state: FlowState, directive: Directive) -> str:
        fallback = get_prompt_config().guardrails.fallback
        template = {Directive.WRAP_UP: fallback.wrap_up, Directive.CLOSE: fallback.close}.get(directive, fallback.topic)
        topic = TOPIC_BY_ID.get(state.current_topic or "")
        return template.strip().format(
            first_name=first_name(interview.employee_name),
            company=self.settings.company_name,
            topic_title=topic.title if topic else "",
            topic_goal=topic.goal if topic else "",
        )

    @staticmethod
    def _mark_completed(interview: Interview, reason: str) -> None:
        interview.status = "completed"
        interview.completed_at = utcnow()
        interview.completion_reason = reason

    @staticmethod
    def _last_assistant_text(interview: Interview) -> str:
        for message in reversed(interview.messages):
            if message.role == "assistant" and not is_blocked(message):
                return message.content
        return ""
