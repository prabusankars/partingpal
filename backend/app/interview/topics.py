"""Interview topics and report categories, defined in prompts.toml."""

from .prompt_config import Topic, get_prompt_config

_config = get_prompt_config()

# Asked in this order. Each topic is asked once, with a capped number of follow-ups.
TOPICS: list[Topic] = _config.topics

TOPIC_BY_ID = {t.id: t for t in TOPICS}

# Fixed categories so the reports can aggregate reasons across interviews.
REASON_CATEGORIES: list[str] = _config.summary.reason_categories


def titles(topic_ids: list[str]) -> list[str]:
    return [TOPIC_BY_ID[t].title for t in topic_ids if t in TOPIC_BY_ID]
