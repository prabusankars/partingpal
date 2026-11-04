import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal


class LLMError(Exception):
    """Raised when a provider call fails or returns nothing usable."""


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class LLMProvider(ABC):
    name: str
    supports_transcription: bool = False

    @abstractmethod
    def complete(
        self,
        model: str,
        system: str,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> str:
        """Return the assistant's text reply."""

    def transcribe(self, audio: bytes, mime_type: str) -> str:
        raise LLMError(f"{self.name} does not support transcription")


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Remove <think> blocks emitted by reasoning models such as Qwen3 or DeepSeek-R1."""
    return _THINK_RE.sub("", text).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from a model reply, tolerating code fences and surrounding prose."""
    text = strip_reasoning(text)
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("No JSON object in model reply")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from model: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMError("Model JSON is not an object")
    return value
