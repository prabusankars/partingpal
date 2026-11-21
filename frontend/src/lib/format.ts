export function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export const STATUS_LABELS: Record<string, string> = {
  pending: "Not started",
  in_progress: "In progress",
  completed: "Completed",
};

export const COMPLETION_LABELS: Record<string, string> = {
  completed: "Finished all topics",
  employee_ended: "Employee asked to stop",
  ended_early: "Ended early by employee",
  turn_limit: "Reached turn limit",
  guardrail_ended: "Ended: conversation went off-topic",
  escalated_to_hr: "Escalated to HR: follow-up needed",
};

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
