import logging
from collections.abc import Callable

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from ..llm.base import ChatMessage, LLMError, LLMProvider, parse_json_object
from ..llm.registry import get_provider
from ..models import Interview
from .guardrails import is_blocked
from .prompt_config import get_prompt_config
from .prompts import summary_system_prompt
from .topics import REASON_CATEGORIES

log = logging.getLogger(__name__)


class KeyReason(BaseModel):
    category: str
    detail: str = ""

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        match = next((c for c in REASON_CATEGORIES if c.lower() == value.strip().lower()), None)
        return match or "Other"


class InterviewAnalysis(BaseModel):
    summary: str = Field(min_length=1)
    key_reasons: list[KeyReason] = Field(default_factory=list, max_length=5)
    sentiment_score: float

    @field_validator("sentiment_score")
    @classmethod
    def clamp(cls, value: float) -> float:
        return max(0.0, min(10.0, value))


def transcript_text(interview: Interview) -> str:
    lines = []
    withheld = get_prompt_config().guardrails.withheld_placeholder
    for m in interview.messages:
        if m.hidden or (m.role == "assistant" and is_blocked(m)):
            continue
        speaker = "Interviewer" if m.role == "assistant" else "Employee"
        # Blocked messages could try to steer the summary, so the model never sees their text.
        lines.append(f"{speaker}: {withheld if is_blocked(m) else m.content}")
    return "\n".join(lines)


def analyse(llm: LLMProvider, interview: Interview, attempts: int = 2) -> InterviewAnalysis:
    # The transcript goes in the user turn, never into the system instruction.
    request = [ChatMessage("user", f"Exit interview transcript:\n\n{transcript_text(interview)}")]
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            raw = llm.complete(interview.model, summary_system_prompt(), request, json_mode=True, temperature=0.2)
            return InterviewAnalysis.model_validate(parse_json_object(raw))
        except (LLMError, ValidationError) as exc:
            last_error = exc
    raise LLMError(f"Summary failed after {attempts} attempts: {last_error}")


def summarise_interview(db: Session, interview: Interview) -> None:
    """Store the analysis, or the error so HR can retry. Status stays 'completed' either way."""
    try:
        result = analyse(get_provider(interview.provider), interview)
    except LLMError as exc:
        log.error("Summary failed for interview %s: %s", interview.id, exc)
        interview.summary_error = str(exc)[:1000]
    else:
        interview.summary = result.summary
        interview.key_reasons = [r.model_dump() for r in result.key_reasons]
        interview.sentiment_score = result.sentiment_score
        interview.summary_error = None
    db.commit()


def summarise_in_background(interview_id: int, session_factory: Callable[[], Session]) -> None:
    db = session_factory()
    try:
        interview = db.get(Interview, interview_id)
        if interview is not None:
            summarise_interview(db, interview)
    finally:
        db.close()
