import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; treat naive timestamps as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32))
    employee_name: Mapped[str] = mapped_column(String(255))
    employee_email: Mapped[str] = mapped_column(String(255), index=True)
    department: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(255))

    # pending | in_progress | completed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # completed | employee_ended | turn_limit | ended_early
    completion_reason: Mapped[str | None] = mapped_column(String(32))

    # Conversation flow state, persisted so any server instance can continue the interview.
    phase: Mapped[str] = mapped_column(String(20), default="topics")  # topics | wrap_up | closing | done
    current_topic_index: Mapped[int] = mapped_column(Integer, default=0)
    followups_used: Mapped[int] = mapped_column(Integer, default=0)
    covered_topics: Mapped[list] = mapped_column(JSON, default=list)
    declined_topics: Mapped[list] = mapped_column(JSON, default=list)
    user_turns: Mapped[int] = mapped_column(Integer, default=0)

    # Analysis
    summary: Mapped[str | None] = mapped_column(Text)
    key_reasons: Mapped[list | None] = mapped_column(JSON)  # [{"category": ..., "detail": ...}]
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    summary_error: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="interview", order_by="Message.id", cascade="all, delete-orphan"
    )

    @property
    def is_expired(self) -> bool:
        return self.status != "completed" and as_utc(self.expires_at) < utcnow()


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    # Kick-off message sent to the model on the employee's behalf; never shown in the UI.
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    # Topic the assistant message was asking about, or the directive (wrap_up/close).
    topic: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="messages")
