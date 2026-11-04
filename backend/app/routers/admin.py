"""HR endpoints. Every route requires a verified, allow-listed Google account."""

import csv
import io
from collections import Counter, defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..config import get_settings
from ..db import get_db
from ..emailer import email_configured, send_invitation
from ..interview.summary import summarise_interview
from ..llm.base import LLMError
from ..llm.registry import list_providers, resolve_model
from ..models import Interview, utcnow
from ..schemas import (
    CountItem,
    DepartmentItem,
    InterviewCreate,
    InterviewCreated,
    InterviewDetailOut,
    InterviewSummaryOut,
    ProvidersOut,
    ReportOut,
)
from .common import interview_link, summary_out, topic_progress, visible_messages

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _get(db: Session, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return interview


@router.get("/me")
def me(email: str = Depends(require_admin)):
    return {"email": email}


@router.get("/providers", response_model=ProvidersOut)
def providers():
    s = get_settings()
    return ProvidersOut(
        default_provider=s.default_provider,
        providers=[p.__dict__ for p in list_providers()],
        email_enabled=email_configured(),
    )


@router.post("/interviews", response_model=InterviewCreated, status_code=status.HTTP_201_CREATED)
def create_interview(body: InterviewCreate, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    s = get_settings()
    try:
        provider, model = resolve_model(body.provider, body.model)
    except LLMError as exc:
        raise HTTPException(422, str(exc))
    interview = Interview(
        employee_name=body.employee_name.strip(),
        employee_email=body.employee_email.lower(),
        department=body.department.strip(),
        provider=provider,
        model=model,
        created_by=admin,
        expires_at=utcnow() + timedelta(days=s.link_valid_days),
    )
    db.add(interview)
    db.commit()
    email_sent = body.send_email and send_invitation(
        interview.employee_email, interview.employee_name, interview_link(interview), s.link_valid_days
    )
    return {**summary_out(interview), "email_sent": email_sent}


@router.get("/interviews", response_model=list[InterviewSummaryOut])
def list_interviews(
    q: str | None = Query(default=None, max_length=255),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = select(Interview).order_by(Interview.created_at.desc())
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Interview.employee_name).like(pattern), Interview.employee_email.like(pattern)))
    if status_filter:
        query = query.where(Interview.status == status_filter)
    return [summary_out(i) for i in db.scalars(query.limit(500))]


@router.get("/interviews/{interview_id}", response_model=InterviewDetailOut)
def get_interview(interview_id: int, db: Session = Depends(get_db)):
    interview = _get(db, interview_id)
    return {
        **summary_out(interview),
        "messages": visible_messages(interview),
        "topics": topic_progress(interview),
        "user_turns": interview.user_turns,
    }


@router.post("/interviews/{interview_id}/summarize", response_model=InterviewSummaryOut)
def regenerate_summary(interview_id: int, db: Session = Depends(get_db)):
    interview = _get(db, interview_id)
    if interview.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only completed interviews can be summarised")
    summarise_interview(db, interview)
    return summary_out(interview)


@router.post("/interviews/{interview_id}/extend", response_model=InterviewSummaryOut)
def extend_link(interview_id: int, db: Session = Depends(get_db)):
    interview = _get(db, interview_id)
    if interview.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    interview.expires_at = utcnow() + timedelta(days=get_settings().link_valid_days)
    db.commit()
    return summary_out(interview)


@router.delete("/interviews/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, interview_id))
    db.commit()


@router.get("/reports", response_model=ReportOut)
def report(db: Session = Depends(get_db)):
    interviews = list(db.scalars(select(Interview)))
    completed = [i for i in interviews if i.status == "completed"]
    scored = [i.sentiment_score for i in completed if i.sentiment_score is not None]

    reasons = Counter(r["category"] for i in completed for r in (i.key_reasons or []) if isinstance(r, dict))
    by_dept: dict[str, list[Interview]] = defaultdict(list)
    for i in completed:
        by_dept[i.department].append(i)
    monthly = Counter(i.completed_at.strftime("%Y-%m") for i in completed if i.completed_at)

    def avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    return ReportOut(
        total_invited=len(interviews),
        total_completed=len(completed),
        in_progress=sum(1 for i in interviews if i.status == "in_progress"),
        completion_rate=round(len(completed) / len(interviews), 3) if interviews else 0.0,
        avg_sentiment=avg(scored),
        reasons=[CountItem(label=k, count=v) for k, v in reasons.most_common()],
        departments=sorted(
            (
                DepartmentItem(
                    department=dept,
                    count=len(items),
                    avg_sentiment=avg([i.sentiment_score for i in items if i.sentiment_score is not None]),
                )
                for dept, items in by_dept.items()
            ),
            key=lambda d: d.count,
            reverse=True,
        ),
        monthly=[CountItem(label=k, count=v) for k, v in sorted(monthly.items())],
        completion_reasons=[
            CountItem(label=k, count=v) for k, v in Counter(i.completion_reason or "completed" for i in completed).most_common()
        ],
    )


@router.get("/reports/export.csv")
def export_csv(db: Session = Depends(get_db)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Email", "Department", "Status", "Completed at", "Sentiment", "Reasons", "Summary"])
    for i in db.scalars(select(Interview).order_by(Interview.created_at.desc())):
        reasons = "; ".join(f"{r['category']}: {r.get('detail', '')}" for r in (i.key_reasons or []) if isinstance(r, dict))
        writer.writerow([
            i.employee_name,
            i.employee_email,
            i.department,
            i.status,
            i.completed_at.isoformat() if i.completed_at else "",
            "" if i.sentiment_score is None else i.sentiment_score,
            reasons,
            i.summary or "",
        ])
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="exit-interviews.csv"'},
    )
