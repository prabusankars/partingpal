import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { InterviewDetail as Detail, Providers } from "../api";
import { useAdmin, useErrorMessage } from "../auth";
import StatusBadge from "../components/StatusBadge";
import TopicProgressBar from "../components/TopicProgressBar";
import { COMPLETION_LABELS, formatDate } from "../lib/format";

export default function InterviewDetail() {
  const { id } = useParams();
  const api = useAdmin();
  const toMessage = useErrorMessage();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<Providers | null>(null);
  const [modelChoice, setModelChoice] = useState<{ provider: string; model: string } | null>(null);

  const load = useCallback(() => {
    api
      .get(Number(id))
      .then(setDetail)
      .catch((err) => setError(toMessage(err)));
  }, [api, id, toMessage]);

  useEffect(load, [load]);

  async function act(action: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await action();
      load();
      return true;
    } catch (err) {
      setError(toMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  function editModel() {
    if (!detail) return;
    setModelChoice({ provider: detail.provider, model: detail.model });
    if (!providers) api.providers().then(setProviders).catch((err) => setError(toMessage(err)));
  }

  if (!detail) return error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>;

  const completed = detail.status === "completed";
  // The summary is produced in the background right after the interview ends.
  const summaryPending = completed && !detail.summary && !detail.summary_error;
  const available = providers?.providers.filter((p) => p.available) ?? [];
  const choiceModels = available.find((p) => p.id === modelChoice?.provider)?.models ?? [];
  const modelUnchanged = modelChoice?.provider === detail.provider && modelChoice?.model === detail.model;
  const modelNote =
    detail.status === "pending"
      ? "Used for the whole interview."
      : detail.status === "in_progress"
        ? "Takes effect from the employee's next message."
        : "Used the next time you regenerate the summary.";

  return (
    <>
      <Link to="/admin" className="small">
        ← All interviews
      </Link>
      <section className="card">
        <div className="section-head">
          <h2>{detail.employee_name}</h2>
          <StatusBadge status={detail.status} expired={detail.expired} />
        </div>
        <dl className="facts">
          <dt>Email</dt>
          <dd>{detail.employee_email}</dd>
          <dt>Department</dt>
          <dd>{detail.department}</dd>
          <dt>Model</dt>
          <dd>
            {modelChoice ? (
              <div className="model-edit">
                <select
                  id="model-provider"
                  aria-label="Provider"
                  value={modelChoice.provider}
                  disabled={!providers}
                  onChange={(e) => {
                    const next = available.find((p) => p.id === e.target.value);
                    setModelChoice({ provider: e.target.value, model: next?.models[0] ?? "" });
                  }}
                >
                  {!providers && <option value={modelChoice.provider}>{modelChoice.provider}</option>}
                  {available.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <select
                  id="model-name"
                  aria-label="Model"
                  value={modelChoice.model}
                  disabled={!providers}
                  onChange={(e) => setModelChoice({ ...modelChoice, model: e.target.value })}
                >
                  {!choiceModels.includes(modelChoice.model) && <option value={modelChoice.model}>{modelChoice.model}</option>}
                  {choiceModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <button
                  className="primary small"
                  disabled={busy || !providers || modelUnchanged || !choiceModels.includes(modelChoice.model)}
                  onClick={async () => {
                    if (await act(() => api.changeModel(detail.id, modelChoice))) setModelChoice(null);
                  }}
                >
                  {busy ? "Saving…" : "Save"}
                </button>
                <button className="ghost small" disabled={busy} onClick={() => setModelChoice(null)}>
                  Cancel
                </button>
                <span className="muted small">{modelNote}</span>
              </div>
            ) : (
              <>
                {detail.provider} · {detail.model}{" "}
                <button className="link small" onClick={editModel}>
                  Change
                </button>
              </>
            )}
          </dd>
          <dt>Created</dt>
          <dd>{formatDate(detail.created_at)}</dd>
          {completed ? (
            <>
              <dt>Completed</dt>
              <dd>
                {formatDate(detail.completed_at)} · {COMPLETION_LABELS[detail.completion_reason ?? ""] ?? detail.completion_reason}
              </dd>
            </>
          ) : (
            <>
              <dt>Link expires</dt>
              <dd>{formatDate(detail.expires_at)}</dd>
            </>
          )}
          <dt>Employee replies</dt>
          <dd>{detail.user_turns}</dd>
        </dl>
        {detail.completion_reason === "escalated_to_hr" && (
          <p className="notice">
            This interview was ended after repeated abusive replies. The employee was told their concerns will be passed
            to the HR executive, who may arrange an in-person session to understand their frustration. Please follow up.
          </p>
        )}
        <div className="actions">
          {!completed && (
            <button className="ghost" disabled={busy} onClick={() => act(() => api.extend(detail.id))}>
              Extend link
            </button>
          )}
          {completed && (
            <button className="ghost" disabled={busy} onClick={() => act(() => api.summarize(detail.id))}>
              {busy ? "Working…" : "Regenerate summary"}
            </button>
          )}
          <button
            className="danger"
            disabled={busy}
            onClick={() => {
              if (!confirm(`Permanently delete the interview with ${detail.employee_name}? This cannot be undone.`)) return;
              setBusy(true);
              api
                .remove(detail.id)
                .then(() => navigate("/admin"))
                .catch((err) => {
                  setError(toMessage(err));
                  setBusy(false);
                });
            }}
          >
            Delete
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </section>

      {completed && (
        <section className="card">
          <h2>Analysis</h2>
          {summaryPending && (
            <p className="muted">
              The summary is being generated. <button className="link" onClick={load}>Refresh</button>
            </p>
          )}
          {detail.summary_error && <p className="error">Summary failed: {detail.summary_error}</p>}
          {detail.summary && <p>{detail.summary}</p>}
          {detail.sentiment_score !== null && (
            <p>
              <strong>Sentiment:</strong> {detail.sentiment_score.toFixed(1)} / 10
            </p>
          )}
          {detail.key_reasons && detail.key_reasons.length > 0 && (
            <ul className="reasons">
              {detail.key_reasons.map((r, i) => (
                <li key={i}>
                  <span className="badge">{r.category}</span> {r.detail}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="card">
        <h2>Topics</h2>
        <TopicProgressBar topics={detail.topics} />
      </section>

      <section className="card">
        <h2>Transcript</h2>
        {detail.messages.length === 0 ? (
          <p className="muted">The employee hasn't started yet.</p>
        ) : (
          <div className="transcript">
            {detail.messages.map((m) => (
              <div key={m.id} className={`bubble bubble-${m.role}`}>
                <div className="bubble-who small muted">{m.role === "assistant" ? "Parting Pal" : detail.employee_name}</div>
                {m.content}
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
