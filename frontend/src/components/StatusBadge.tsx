import { STATUS_LABELS } from "../lib/format";

export default function StatusBadge({ status, expired }: { status: string; expired?: boolean }) {
  if (expired) return <span className="badge badge-expired">Link expired</span>;
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}
