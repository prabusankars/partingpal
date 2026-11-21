"""Builds the model prompts from the templates in prompts.toml."""

from .flow import Directive, FlowState
from .guardrails import sanitise_for_prompt
from .prompt_config import get_prompt_config
from .topics import REASON_CATEGORIES, TOPIC_BY_ID, TOPICS, titles

# Part of the protocol between the model and the code, so it lives here rather than in the prompt file.
COMPLETION_MARKER = "[INTERVIEW_COMPLETE]"


def _list(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def first_name(name: str) -> str:
    return name.split()[0] if name.strip() else "there"


def kickoff_message() -> str:
    return get_prompt_config().interviewer.kickoff


def repeat_correction() -> str:
    return get_prompt_config().interviewer.repeat_correction


def leak_correction() -> str:
    return get_prompt_config().interviewer.leak_correction


def interviewer_system_prompt(
    *, name: str, department: str, company: str, state: FlowState, directive: Directive
) -> str:
    config = get_prompt_config().interviewer
    topic = TOPIC_BY_ID.get(state.current_topic or "")
    upcoming = [t for t in state.remaining if t != (topic.id if topic else None)]
    if directive in (Directive.WRAP_UP, Directive.CLOSE):
        upcoming = []
    task = getattr(config.tasks, directive.value).format(
        first_name=first_name(name),
        topic_title=topic.title if topic else "",
        topic_goal=topic.goal if topic else "",
        company=company,
        marker=COMPLETION_MARKER,
    )
    return config.system.strip().format(
        name=name,
        first_name=first_name(name),
        department=department,
        company=company,
        covered=_list(titles(list(state.covered))),
        declined=_list(titles(list(state.declined))),
        upcoming=_list(titles(upcoming)),
        task=task,
        marker=COMPLETION_MARKER,
    )


def classifier_system_prompt() -> str:
    return get_prompt_config().classifier.system.strip().format(topic_ids=", ".join(t.id for t in TOPICS))


def classifier_user_prompt(*, topic_title: str, topic_id: str, question: str, answer: str) -> str:
    return get_prompt_config().classifier.user.strip().format(
        topic_title=topic_title, topic_id=topic_id, question=question, answer=sanitise_for_prompt(answer)
    )


def summary_system_prompt() -> str:
    return get_prompt_config().summary.system.strip().format(categories=", ".join(f'"{c}"' for c in REASON_CATEGORIES))
