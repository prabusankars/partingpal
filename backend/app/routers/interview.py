"""Public endpoints used by the employee, authorised by the unguessable interview token."""

import logging
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, get_session_factory
from ..interview.engine import InterviewEngine
from ..interview.summary import summarise_in_background
from ..llm.base import LLMError
from ..llm.registry import get_provider, get_transcriber
from ..models import Interview
from ..schemas import PublicState, SendMessage, Transcript
from .common import topic_progress, visible_messages

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interview", tags=["interview"])

INVALID_LINK = "This interview link is invalid or has expired."


def _load(db: Session, token: str, *, lock: bool = False) -> Interview:
    query = select(Interview).where(Interview.token == token)
    if lock:
        # Serialises concurrent submits (double clicks, two tabs) on Postgres.
        query = query.with_for_update()
    interview = db.scalars(query).one_or_none()
    if interview is None or interview.is_expired:
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVALID_LINK)
    return interview


def _state(interview: Interview, *, just_finished: bool = False) -> PublicState:
    s = get_settings()
    # A completed transcript is not shown again in case the link was forwarded,
    # except in the response that delivers the closing message.
    hide = interview.status == "completed" and not just_finished
    return PublicState(
        first_name=interview.employee_name.split()[0],
        company=s.company_name,
        status=interview.status,
        messages=[] if hide else visible_messages(interview),
        topics=topic_progress(interview),
        transcription_available=get_transcriber() is not None,
        max_message_chars=s.max_message_chars,
    )


def _engine(interview: Interview) -> InterviewEngine:
    try:
        return InterviewEngine(get_provider(interview.provider), get_settings())
    except LLMError as exc:
        log.error("Provider unavailable for interview %s: %s", interview.id, exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The interview assistant is unavailable right now.")


def _run(db: Session, interview: Interview, action: Callable[[], object]) -> None:
    """Run an engine step atomically: if the model fails, nothing (not even the user's message) is saved."""
    try:
        action()
        db.commit()
    except LLMError as exc:
        db.rollback()
        log.error("LLM failure for interview %s: %s", interview.id, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Parting Pal couldn't respond just now. Please try sending again."
        )


@router.get("/{token}", response_model=PublicState)
def get_state(token: str, db: Session = Depends(get_db)):
    return _state(_load(db, token))


@router.post("/{token}/start", response_model=PublicState)
def start(token: str, db: Session = Depends(get_db)):
    interview = _load(db, token, lock=True)
    if interview.status == "pending":
        engine = _engine(interview)
        _run(db, interview, lambda: engine.start(interview))
    # Starting twice (refresh, second tab) just returns the current conversation.
    return _state(interview)


@router.post("/{token}/messages", response_model=PublicState)
def send_message(
    token: str,
    body: SendMessage,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    s = get_settings()
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Message is empty")
    if len(text) > s.max_message_chars:
        raise HTTPException(422, f"Please keep messages under {s.max_message_chars} characters")
    interview = _load(db, token, lock=True)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is not in progress")
    engine = _engine(interview)
    _run(db, interview, lambda: engine.respond(interview, text))
    if interview.status == "completed":
        background.add_task(summarise_in_background, interview.id, session_factory)
    return _state(interview, just_finished=True)


@router.post("/{token}/complete", response_model=PublicState)
def complete(
    token: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    interview = _load(db, token, lock=True)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is not in progress")
    InterviewEngine.end_early(interview)  # no model call needed
    db.commit()
    background.add_task(summarise_in_background, interview.id, session_factory)
    return _state(interview)


@router.post("/{token}/transcribe", response_model=Transcript)
def transcribe(token: str, audio: UploadFile = File(...), db: Session = Depends(get_db)):
    """Return text for the employee to review and edit before sending; nothing is stored."""
    s = get_settings()
    interview = _load(db, token)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is not in progress")
    transcriber = get_transcriber()
    if transcriber is None:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Voice input is not available")
    data = audio.file.read(s.max_audio_bytes + 1)
    if len(data) > s.max_audio_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Recording is too long")
    if not data:
        raise HTTPException(422, "Recording is empty")
    try:
        text = transcriber.transcribe(data, audio.content_type or "audio/wav")
    except LLMError as exc:
        log.error("Transcription failed for interview %s: %s", interview.id, exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't transcribe the recording. Please try again or type your answer.")
    if not text:
        raise HTTPException(422, "No speech was detected in the recording")
    return Transcript(text=text)
