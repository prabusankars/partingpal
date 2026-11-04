import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { InterviewSummary, Providers } from "../api";
import { useAdmin, useErrorMessage } from "../auth";
import StatusBadge from "../components/StatusBadge";
import { copyText, formatDate } from "../lib/format";

function CopyLinkButton({ link }: { link: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="ghost small"
      onClick={async () => {
        setCopied(await copyText(link));
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied" : "Copy link"}
    </button>
  );
}

function NewInterviewForm({ onCreated }: { onCreated: () => void }) {
  const api = useAdmin();
  const toMessage = useErrorMessage();
  const [providers, setProviders] = useState<Providers | null>(null);
  const [form, setForm] = useState({ employee_name: "", employee_email: "", department: "", provider: "", model: "", send_email: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<(InterviewSummary & { email_sent: boolean }) | null>(null);

  useEffect(() => {
    api
      .providers()
      .then((p) => {
        setProviders(p);
        const usable = p.providers.filter((x) => x.available);
        const initial = usable.find((x) => x.id === p.default_provider) ?? usable[0];
        if (initial) setForm((f) => ({ ...f, provider: initial.id, model: initial.models[0] ?? "", send_email: p.email_enabled }));
      })
      .catch((err) => setError(toMessage(err)));
  }, [api, toMessage]);

  const available = providers?.providers.filter((p) => p.available) ?? [];
  const models = available.find((p) => p.id === form.provider)?.models ?? [];

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setCreated(await api.create(form));
      setForm((f) => ({ ...f, employee_name: "", employee_email: "", department: "" }));
      onCreated();
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Invite a departing employee</h2>
      <form className="form-grid" onSubmit={submit}>
        <label>
          Name
          <input required maxLength={255} value={form.employee_name} onChange={(e) => setForm({ ...form, employee_name: e.target.value })} />
        </label>
        <label>
          Email
          <input required type="email" value={form.employee_email} onChange={(e) => setForm({ ...form, employee_email: e.target.value })} />
        </label>
        <label>
          Department
          <input required maxLength={255} value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
        </label>
        <label>
          AI provider
          <select
            value={form.provider}
            onChange={(e) => {
              const next = available.find((p) => p.id === e.target.value);
              setForm({ ...form, provider: e.target.value, model: next?.models[0] ?? "" });
            }}
          >
            {providers?.providers.map((p) => (
              <option key={p.id} value={p.id} disabled={!p.available}>
                {p.label}
                {p.available ? "" : " (not configured)"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model
          <select value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}>
            {models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <label className="checkbox" title={providers?.email_enabled ? "" : "SMTP is not configured on the server"}>
          <input
            type="checkbox"
            checked={form.send_email}
            disabled={!providers?.email_enabled}
            onChange={(e) => setForm({ ...form, send_email: e.target.checked })}
          />
          Email the link to the employee
        </label>
        <div className="form-actions">
          <button className="primary" disabled={busy || available.length === 0}>
            {busy ? "Creating…" : "Create interview"}
          </button>
          {providers && available.length === 0 && <span className="error">No AI provider is configured on the server.</span>}
        </div>
      </form>
      {error && <p className="error">{error}</p>}
      {created && (
        <div className="notice">
          <strong>Interview created for {created.employee_name}.</strong>{" "}
          {created.email_sent ? "The link was emailed to them." : "No email was sent, so share this link with them:"}
          <div className="link-row">
            <code>{created.link}</code>
            <CopyLinkButton link={created.link} />
          </div>
        </div>
      )}
    </section>
  );
}

export default function Dashboard() {
  const api = useAdmin();
  const toMessage = useErrorMessage();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState<InterviewSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const handle = setTimeout(() => {
      api
        .list(query.trim(), status)
        .then((r) => {
          setRows(r);
          setError(null);
        })
        .catch((err) => setError(toMessage(err)));
    }, 250);
    return () => clearTimeout(handle);
  }, [api, query, status, refresh, toMessage]);

  return (
    <>
      <NewInterviewForm onCreated={() => setRefresh((n) => n + 1)} />
      <section className="card">
        <div className="section-head">
          <h2>Interviews</h2>
          <input className="search" placeholder="Search name or email" value={query} onChange={(e) => setQuery(e.target.value)} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="pending">Not started</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        {error && <p className="error">{error}</p>}
        {rows === null ? (
          <p className="muted">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="muted">No interviews match.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Model</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/admin/interviews/${r.id}`}>{r.employee_name}</Link>
                      <div className="muted small">{r.employee_email}</div>
                    </td>
                    <td>{r.department}</td>
                    <td>
                      <StatusBadge status={r.status} expired={r.expired} />
                    </td>
                    <td className="small">
                      {r.provider} · {r.model}
                    </td>
                    <td className="small">{formatDate(r.created_at)}</td>
                    <td>{r.status !== "completed" && !r.expired && <CopyLinkButton link={r.link} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
