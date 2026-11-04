from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ProviderOut(BaseModel):
    id: str
    label: str
    models: list[str]
    available: bool


class ProvidersOut(BaseModel):
    default_provider: str
    providers: list[ProviderOut]
    email_enabled: bool


class InterviewCreate(BaseModel):
    employee_name: str = Field(min_length=1, max_length=255)
    employee_email: EmailStr
    department: str = Field(min_length=1, max_length=255)
    provider: str | None = None
    model: str | None = None
    send_email: bool = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


class KeyReasonOut(BaseModel):
    category: str
    detail: str = ""


class InterviewSummaryOut(BaseModel):
    id: int
    employee_name: str
    employee_email: str
    department: str
    status: str
    provider: str
    model: str
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime
    expired: bool
    completion_reason: str | None
    summary: str | None
    key_reasons: list[KeyReasonOut] | None
    sentiment_score: float | None
    summary_error: str | None
    link: str


class InterviewCreated(InterviewSummaryOut):
    email_sent: bool


class TopicProgress(BaseModel):
    id: str
    title: str
    state: str  # covered | declined | current | upcoming


class InterviewDetailOut(InterviewSummaryOut):
    messages: list[MessageOut]
    topics: list[TopicProgress]
    user_turns: int


class PublicState(BaseModel):
    first_name: str
    company: str
    status: str
    messages: list[MessageOut]
    topics: list[TopicProgress]
    transcription_available: bool
    max_message_chars: int


class SendMessage(BaseModel):
    text: str = Field(min_length=1)


class Transcript(BaseModel):
    text: str


class CountItem(BaseModel):
    label: str
    count: int


class DepartmentItem(BaseModel):
    department: str
    count: int
    avg_sentiment: float | None


class ReportOut(BaseModel):
    total_invited: int
    total_completed: int
    in_progress: int
    completion_rate: float
    avg_sentiment: float | None
    reasons: list[CountItem]
    departments: list[DepartmentItem]
    monthly: list[CountItem]
    completion_reasons: list[CountItem]
