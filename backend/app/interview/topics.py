from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    goal: str


# Asked in this order. Each topic is asked once, with a capped number of follow-ups.
TOPICS: list[Topic] = [
    Topic("reasons_for_leaving", "Primary reasons for leaving",
          "the main reasons behind their decision to leave and what triggered it"),
    Topic("job_satisfaction", "Overall job satisfaction",
          "how satisfied they were with their role and day-to-day work"),
    Topic("manager_relationship", "Relationship with their manager",
          "the support, communication and feedback they received from their manager"),
    Topic("team_and_colleagues", "Team and colleagues",
          "collaboration and relationships within their team and with colleagues"),
    Topic("work_life_balance", "Work-life balance",
          "workload, working hours, flexibility and stress"),
    Topic("career_development", "Career development",
          "growth, learning and promotion opportunities"),
    Topic("compensation_benefits", "Compensation and benefits",
          "how pay and benefits compared with their expectations and the market"),
    Topic("suggestions", "Suggestions for improvement",
          "what the company could do better, or what might have made them stay"),
]

TOPIC_BY_ID = {t.id: t for t in TOPICS}

# Fixed categories so the reports can aggregate reasons across interviews.
REASON_CATEGORIES = [
    "Compensation",
    "Career growth",
    "Management",
    "Work-life balance",
    "Culture",
    "Team",
    "Role fit",
    "Better opportunity",
    "Relocation",
    "Personal",
    "Other",
]


def titles(topic_ids: list[str]) -> list[str]:
    return [TOPIC_BY_ID[t].title for t in topic_ids if t in TOPIC_BY_ID]
