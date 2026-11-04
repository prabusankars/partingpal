from ..config import get_settings
from ..interview.topics import TOPICS
from ..models import Interview, as_utc
from ..schemas import InterviewSummaryOut, MessageOut, TopicProgress


def interview_link(interview: Interview) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/interview/{interview.token}"


def topic_progress(interview: Interview) -> list[TopicProgress]:
    covered = set(interview.covered_topics or ())
    declined = set(interview.declined_topics or ())
    in_topics = interview.status == "in_progress" and interview.phase == "topics"
    result = []
    for index, topic in enumerate(TOPICS):
        if topic.id in covered:
            state = "covered"
        elif topic.id in declined:
            state = "declined"
        elif in_topics and index == interview.current_topic_index:
            state = "current"
        else:
            state = "upcoming"
        result.append(TopicProgress(id=topic.id, title=topic.title, state=state))
    return result


def visible_messages(interview: Interview) -> list[MessageOut]:
    return [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=as_utc(m.created_at))
        for m in interview.messages
        if not m.hidden
    ]


def summary_out(interview: Interview) -> dict:
    return InterviewSummaryOut(
        id=interview.id,
        employee_name=interview.employee_name,
        employee_email=interview.employee_email,
        department=interview.department,
        status=interview.status,
        provider=interview.provider,
        model=interview.model,
        created_at=as_utc(interview.created_at),
        completed_at=as_utc(interview.completed_at),
        expires_at=as_utc(interview.expires_at),
        expired=interview.is_expired,
        completion_reason=interview.completion_reason,
        summary=interview.summary,
        key_reasons=interview.key_reasons,
        sentiment_score=interview.sentiment_score,
        summary_error=interview.summary_error,
        link=interview_link(interview),
    ).model_dump()
