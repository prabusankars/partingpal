import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Report } from "../api";
import { useAdmin, useErrorMessage } from "../auth";
import { COMPLETION_LABELS } from "../lib/format";

const BAR = "#4f7cff";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="muted small">{label}</div>
    </div>
  );
}

export default function Reports() {
  const api = useAdmin();
  const toMessage = useErrorMessage();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .report()
      .then(setReport)
      .catch((err) => setError(toMessage(err)));
  }, [api, toMessage]);

  async function exportCsv() {
    try {
      const blob = await api.exportCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "exit-interviews.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(toMessage(err));
    }
  }

  if (!report) return error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>;

  const reasonHeight = Math.max(160, report.reasons.length * 36);

  return (
    <>
      <section className="card">
        <div className="section-head">
          <h2>Overview</h2>
          <button className="ghost" onClick={exportCsv}>
            Export CSV
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        <div className="stats">
          <Stat label="Invited" value={report.total_invited} />
          <Stat label="Completed" value={report.total_completed} />
          <Stat label="In progress" value={report.in_progress} />
          <Stat label="Completion rate" value={`${Math.round(report.completion_rate * 100)}%`} />
          <Stat label="Avg. sentiment (0–10)" value={report.avg_sentiment ?? "—"} />
        </div>
      </section>

      {report.total_completed === 0 ? (
        <section className="card">
          <p className="muted">Charts appear once interviews are completed.</p>
        </section>
      ) : (
        <>
          <section className="card">
            <h2>Reasons for leaving</h2>
            <ResponsiveContainer width="100%" height={reasonHeight}>
              <BarChart data={report.reasons} layout="vertical" margin={{ left: 24, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={140} />
                <Tooltip />
                <Bar dataKey="count" name="Mentions" fill={BAR} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <div className="grid-2">
            <section className="card">
              <h2>By department</h2>
              <table>
                <thead>
                  <tr>
                    <th>Department</th>
                    <th>Exits</th>
                    <th>Avg. sentiment</th>
                  </tr>
                </thead>
                <tbody>
                  {report.departments.map((d) => (
                    <tr key={d.department}>
                      <td>{d.department}</td>
                      <td>{d.count}</td>
                      <td>{d.avg_sentiment ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section className="card">
              <h2>Completed per month</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={report.monthly}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" name="Interviews" fill={BAR} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </section>
          </div>

          <section className="card">
            <h2>How interviews ended</h2>
            <ul className="plain">
              {report.completion_reasons.map((c) => (
                <li key={c.label}>
                  {COMPLETION_LABELS[c.label] ?? c.label}: <strong>{c.count}</strong>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </>
  );
}
