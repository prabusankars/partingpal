"""Prompts, topics and guardrail settings, loaded from a TOML file so they can be improved without code changes.

The default file is app/interview/prompts.toml. Set PROMPTS_FILE to use another copy. The file is read and
validated once at startup, so restart the backend after editing it.
"""

import re
import tomllib
from functools import lru_cache
from pathlib import Path
from string import Formatter

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ..config import get_settings

DEFAULT_PATH = Path(__file__).with_name("prompts.toml")


class PromptConfigError(RuntimeError):
    pass


def _placeholders(template: str) -> set[str]:
    try:
        return {field for _, field, _, _ in Formatter().parse(template) if field is not None}
    except ValueError as exc:  # e.g. a single "{" that should have been "{{"
        raise ValueError(f"{exc} (write literal braces as {{{{ and }}}})") from exc


def _check(template: str, where: str, allowed: set[str], required: set[str] = frozenset()) -> str:
    """Catch template mistakes at startup instead of in the middle of someone's interview."""
    used = _placeholders(template)
    unknown = used - allowed
    if unknown:
        raise ValueError(f"{where}: unknown placeholder(s) {sorted(unknown)}; allowed: {sorted(allowed)}")
    missing = set(required) - used
    if missing:
        raise ValueError(f"{where}: must contain {sorted('{' + m + '}' for m in missing)}")
    return template


class Topic(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)


TASK_FIELDS = {"first_name", "topic_title", "topic_goal", "marker", "company"}


class InterviewerTasks(BaseModel):
    open: str
    ask_topic: str
    follow_up: str
    wrap_up: str
    close: str

    @model_validator(mode="after")
    def placeholders(self):
        for name in ("open", "ask_topic", "follow_up", "wrap_up"):
            _check(getattr(self, name), f"interviewer.tasks.{name}", TASK_FIELDS)
        _check(self.close, "interviewer.tasks.close", TASK_FIELDS, {"marker"})
        return self


class Interviewer(BaseModel):
    system: str
    kickoff: str
    repeat_correction: str
    leak_correction: str
    tasks: InterviewerTasks

    @model_validator(mode="after")
    def placeholders(self):
        fields = {"name", "first_name", "department", "company", "covered", "declined", "upcoming", "task", "marker"}
        _check(self.system, "interviewer.system", fields, {"task"})
        for name in ("kickoff", "repeat_correction", "leak_correction"):
            _check(getattr(self, name), f"interviewer.{name}", set())
        return self


class Classifier(BaseModel):
    system: str
    user: str

    @model_validator(mode="after")
    def placeholders(self):
        _check(self.system, "classifier.system", {"topic_ids"}, {"topic_ids"})
        _check(self.user, "classifier.user", {"topic_title", "topic_id", "question", "answer"}, {"answer"})
        return self


class Summary(BaseModel):
    system: str
    reason_categories: list[str] = Field(min_length=1)

    @field_validator("reason_categories")
    @classmethod
    def has_other(cls, value: list[str]) -> list[str]:
        if "Other" not in value:
            raise ValueError('summary.reason_categories must include "Other" (used for unrecognised reasons)')
        return value

    @model_validator(mode="after")
    def placeholders(self):
        _check(self.system, "summary.system", {"categories"})
        return self


class Fallbacks(BaseModel):
    """Used when the model's reply is unusable twice in a row (for example it leaked its instructions)."""

    topic: str
    wrap_up: str
    close: str

    @model_validator(mode="after")
    def placeholders(self):
        for name in ("topic", "wrap_up", "close"):
            _check(getattr(self, name), f"guardrails.fallback.{name}", {"first_name", "company", "topic_title", "topic_goal"})
        return self


class Guardrails(BaseModel):
    max_strikes: int = Field(ge=1)
    max_abusive_messages: int = Field(ge=0)
    escalation_message: str
    redirect_off_topic: str
    redirect_manipulation: str
    end_message: str
    withheld_placeholder: str
    blocked_patterns: list[str] = Field(default_factory=list)
    leak_phrases: list[str] = Field(default_factory=list)
    fallback: Fallbacks

    @field_validator("blocked_patterns")
    @classmethod
    def compiles(cls, value: list[str]) -> list[str]:
        for pattern in value:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"guardrails.blocked_patterns: invalid regex {pattern!r}: {exc}") from exc
        return value

    @model_validator(mode="after")
    def placeholders(self):
        redirect_fields = {"first_name", "company", "question"}
        _check(self.redirect_off_topic, "guardrails.redirect_off_topic", redirect_fields)
        _check(self.redirect_manipulation, "guardrails.redirect_manipulation", redirect_fields)
        _check(self.end_message, "guardrails.end_message", {"first_name", "company"})
        _check(self.escalation_message, "guardrails.escalation_message", {"first_name", "company"})
        _check(self.withheld_placeholder, "guardrails.withheld_placeholder", set())
        return self


class PromptConfig(BaseModel):
    version: str = Field(min_length=1)
    topics: list[Topic] = Field(min_length=1)
    interviewer: Interviewer
    classifier: Classifier
    summary: Summary
    guardrails: Guardrails

    @field_validator("topics")
    @classmethod
    def unique_ids(cls, value: list[Topic]) -> list[Topic]:
        ids = [t.id for t in value]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate topic ids: {duplicates}")
        return value


def load_prompt_config(path: Path | str) -> PromptConfig:
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return PromptConfig.model_validate(data)
    except FileNotFoundError as exc:
        raise PromptConfigError(f"Prompt file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PromptConfigError(f"{path} is not valid TOML: {exc}") from exc
    except ValidationError as exc:
        raise PromptConfigError(f"{path} has invalid settings:\n{exc}") from exc


@lru_cache
def get_prompt_config() -> PromptConfig:
    configured = get_settings().prompts_file
    return load_prompt_config(configured or DEFAULT_PATH)
