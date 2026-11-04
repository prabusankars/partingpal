import type { TopicProgress } from "../api";

const STATE_LABEL: Record<TopicProgress["state"], string> = {
  covered: "Covered",
  declined: "Skipped",
  current: "Now",
  upcoming: "Upcoming",
};

export default function TopicProgressBar({ topics, compact }: { topics: TopicProgress[]; compact?: boolean }) {
  const done = topics.filter((t) => t.state === "covered" || t.state === "declined").length;
  return (
    <div className="topics" aria-label={`${done} of ${topics.length} topics done`}>
      <div className="topics-track">
        {topics.map((t) => (
          <span key={t.id} className={`topic-seg topic-${t.state}`} title={`${t.title}: ${STATE_LABEL[t.state]}`} />
        ))}
      </div>
      {compact ? (
        <span className="muted small">
          {done} of {topics.length} topics
        </span>
      ) : (
        <ul className="topic-list">
          {topics.map((t) => (
            <li key={t.id} className={`topic-${t.state}`}>
              <span className="dot" /> {t.title} <span className="muted small">· {STATE_LABEL[t.state]}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
