import json
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    AUTH_DISABLED="true",
    GEMINI_API_KEY="test-key",
    DEFAULT_PROVIDER="gemini",
    MAX_USER_TURNS="20",
    MAX_FOLLOWUPS_PER_TOPIC="1",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal  # noqa: E402
from app.interview import summary as summary_module  # noqa: E402
from app.interview.prompts import COMPLETION_MARKER  # noqa: E402
from app.llm.base import LLMError, LLMProvider  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import interview as interview_router  # noqa: E402


class FakeLLM(LLMProvider):
    """Scripted model. Employee replies steer the classifier with keywords:
    VAGUE -> not answered, SKIP -> declined, BYE -> wants to end, PAY -> also covers compensation."""

    name = "fake"
    supports_transcription = True

    def __init__(self):
        self.replies = 0
        self.fail = False

    def complete(self, model, system, messages, *, json_mode=False, temperature=0.7):
        if self.fail:
            raise LLMError("simulated outage")
        if system.startswith("You assess"):
            answer = messages[-1].content.split("Employee replied:")[-1]
            return json.dumps({
                "answered": "VAGUE" not in answer,
                "declined": "SKIP" in answer,
                "wants_to_end": "BYE" in answer,
                "also_covered": ["compensation_benefits"] if "PAY" in answer else [],
            })
        if system.startswith("You analyse"):
            return json.dumps({
                "summary": "Left for better growth opportunities.",
                "key_reasons": [{"category": "career growth", "detail": "no promotion path"}],
                "sentiment_score": 12,
            })
        self.replies += 1
        task = system.split("Your task for THIS message only:\n")[1].split("\n")[0]
        marker = f"\n{COMPLETION_MARKER}" if task.startswith("End the interview") else ""
        return f"Reply {self.replies}. {task}{marker}"

    def transcribe(self, audio, mime_type):
        return "transcribed words"


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(interview_router, "get_provider", lambda _: fake)
    monkeypatch.setattr(interview_router, "get_transcriber", lambda: fake)
    monkeypatch.setattr(summary_module, "get_provider", lambda _: fake)
    return fake


@pytest.fixture
def client(llm):
    engine = SessionLocal.kw["bind"]
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def token(client):
    response = client.post(
        "/api/admin/interviews",
        json={"employee_name": "Asha Rao", "employee_email": "Asha@Example.com", "department": "Platform", "send_email": False},
    )
    assert response.status_code == 201, response.text
    return response.json()["link"].rsplit("/", 1)[-1]
