from datetime import timedelta

from app.auth import is_allowed_admin
from app.config import get_settings
from app.db import SessionLocal
from app.interview.prompts import COMPLETION_MARKER
from app.models import Interview, utcnow


def test_full_interview_completes_without_repeating(client, token, llm):
    state = client.post(f"/api/interview/{token}/start").json()
    assert state["status"] == "in_progress"
    assert [m["role"] for m in state["messages"]] == ["assistant"]  # kickoff stays hidden

    # Refreshing or starting again keeps the conversation instead of restarting it.
    assert client.post(f"/api/interview/{token}/start").json()["messages"] == state["messages"]

    replies = 0
    while state["status"] == "in_progress":
        state = client.post(f"/api/interview/{token}/messages", json={"text": "A detailed answer."}).json()
        replies += 1
        assert replies <= get_settings().max_user_turns
        if state["status"] == "in_progress":
            assert COMPLETION_MARKER not in state["messages"][-1]["content"]

    assert replies == 9  # 8 topics + the "anything else?" answer
    assert state["messages"][-1]["role"] == "assistant"  # closing message is delivered
    assert client.get(f"/api/interview/{token}").json()["messages"] == []  # but not exposed again

    with SessionLocal() as db:
        interview = db.query(Interview).one()
        asked = [m.topic for m in interview.messages if m.role == "assistant"]
        topic_questions = [t for t in asked if t not in ("wrap_up", "close")]
        assert len(topic_questions) == len(set(topic_questions)) == 8
        assert asked[-2:] == ["wrap_up", "close"]
        assert COMPLETION_MARKER not in interview.messages[-1].content
        assert interview.completion_reason == "completed"
        assert interview.summary == "Left for better growth opportunities."
        assert interview.key_reasons == [{"category": "Career growth", "detail": "no promotion path"}]
        assert interview.sentiment_score == 10.0

    assert client.post(f"/api/interview/{token}/messages", json={"text": "more"}).status_code == 409


def test_model_failure_does_not_save_the_message(client, token, llm):
    client.post(f"/api/interview/{token}/start")
    llm.fail = True
    response = client.post(f"/api/interview/{token}/messages", json={"text": "hello"})
    assert response.status_code == 502
    llm.fail = False
    messages = client.get(f"/api/interview/{token}").json()["messages"]
    assert [m["role"] for m in messages] == ["assistant"]


def test_end_early_and_summary(client, token):
    client.post(f"/api/interview/{token}/start")
    state = client.post(f"/api/interview/{token}/complete").json()
    assert state["status"] == "completed"
    detail = client.get("/api/admin/interviews/1").json()
    assert detail["completion_reason"] == "ended_early"
    assert detail["summary"]


def test_message_limits_and_unknown_link(client, token):
    client.post(f"/api/interview/{token}/start")
    too_long = "x" * (get_settings().max_message_chars + 1)
    assert client.post(f"/api/interview/{token}/messages", json={"text": too_long}).status_code == 422
    assert client.get("/api/interview/not-a-token").status_code == 404


def test_expired_link(client, token):
    with SessionLocal() as db:
        db.query(Interview).one().expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/api/interview/{token}").status_code == 404


def test_search_and_reports(client, token):
    assert len(client.get("/api/admin/interviews", params={"q": "asha"}).json()) == 1
    assert len(client.get("/api/admin/interviews", params={"q": "example.com"}).json()) == 1
    assert client.get("/api/admin/interviews", params={"q": "nobody"}).json() == []
    report = client.get("/api/admin/reports").json()
    assert report["total_invited"] == 1 and report["total_completed"] == 0
    assert client.get("/api/admin/reports/export.csv").text.startswith("Name,Email")


def test_unknown_provider_rejected(client):
    body = {"employee_name": "A", "employee_email": "a@b.co", "department": "X", "provider": "openai"}
    assert client.post("/api/admin/interviews", json=body).status_code == 422  # no OpenAI key configured


def test_admin_allowlist_fails_closed(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_allowed_emails", "")
    monkeypatch.setattr(settings, "admin_allowed_domains", "")
    assert not is_allowed_admin("hr@acme.com")
    monkeypatch.setattr(settings, "admin_allowed_domains", "acme.com")
    assert is_allowed_admin("HR@acme.com")
    assert not is_allowed_admin("someone@gmail.com")
