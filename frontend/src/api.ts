export type Role = "user" | "assistant";

export interface Message {
  id: number;
  role: Role;
  content: string;
  created_at: string;
}

export interface TopicProgress {
  id: string;
  title: string;
  state: "covered" | "declined" | "current" | "upcoming";
}

export interface PublicState {
  first_name: string;
  company: string;
  status: "pending" | "in_progress" | "completed";
  messages: Message[];
  topics: TopicProgress[];
  transcription_available: boolean;
  max_message_chars: number;
}

export interface KeyReason {
  category: string;
  detail: string;
}

export interface InterviewSummary {
  id: number;
  employee_name: string;
  employee_email: string;
  department: string;
  status: PublicState["status"];
  provider: string;
  model: string;
  created_at: string;
  completed_at: string | null;
  expires_at: string;
  expired: boolean;
  completion_reason: string | null;
  summary: string | null;
  key_reasons: KeyReason[] | null;
  sentiment_score: number | null;
  summary_error: string | null;
  link: string;
}

export interface InterviewDetail extends InterviewSummary {
  messages: Message[];
  topics: TopicProgress[];
  user_turns: number;
}

export interface ProviderInfo {
  id: string;
  label: string;
  models: string[];
  available: boolean;
}

export interface Providers {
  default_provider: string;
  providers: ProviderInfo[];
  email_enabled: boolean;
}

export interface CountItem {
  label: string;
  count: number;
}

export interface Report {
  total_invited: number;
  total_completed: number;
  in_progress: number;
  completion_rate: number;
  avg_sentiment: number | null;
  reasons: CountItem[];
  departments: { department: string; count: number; avg_sentiment: number | null }[];
  monthly: CountItem[];
  completion_reasons: CountItem[];
}

export interface NewInterview {
  employee_name: string;
  employee_email: string;
  department: string;
  provider: string;
  model: string;
  send_email: boolean;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  // Not "Authorization": proxies such as Cloud Shell web preview claim that header for their own sign-in.
  if (token) headers.set("X-Auth-Token", token);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("Content-Type") ?? "";
  return (type.includes("application/json") ? response.json() : response.blob()) as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

// Employee-facing calls, authorised by the link token.
export const interviewApi = {
  get: (token: string) => request<PublicState>(`/api/interview/${token}`),
  start: (token: string) => request<PublicState>(`/api/interview/${token}/start`, { method: "POST" }),
  send: (token: string, text: string) => request<PublicState>(`/api/interview/${token}/messages`, json({ text })),
  complete: (token: string) => request<PublicState>(`/api/interview/${token}/complete`, { method: "POST" }),
  transcribe: (token: string, audio: Blob) => {
    const form = new FormData();
    form.append("audio", audio, "recording.wav");
    return request<{ text: string }>(`/api/interview/${token}/transcribe`, { method: "POST", body: form });
  },
};

// HR calls, authorised by the Google ID token.
export function adminApi(token: string) {
  return {
    me: () => request<{ email: string }>("/api/admin/me", {}, token),
    providers: () => request<Providers>("/api/admin/providers", {}, token),
    list: (q: string, status: string) => {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (status) params.set("status", status);
      return request<InterviewSummary[]>(`/api/admin/interviews?${params}`, {}, token);
    },
    create: (body: NewInterview) =>
      request<InterviewSummary & { email_sent: boolean }>("/api/admin/interviews", json(body), token),
    get: (id: number) => request<InterviewDetail>(`/api/admin/interviews/${id}`, {}, token),
    summarize: (id: number) => request<InterviewSummary>(`/api/admin/interviews/${id}/summarize`, { method: "POST" }, token),
    extend: (id: number) => request<InterviewSummary>(`/api/admin/interviews/${id}/extend`, { method: "POST" }, token),
    changeModel: (id: number, choice: { provider: string; model: string }) =>
      request<InterviewSummary>(`/api/admin/interviews/${id}/model`, { method: "PATCH", body: JSON.stringify(choice) }, token),
    remove: (id: number) => request<void>(`/api/admin/interviews/${id}`, { method: "DELETE" }, token),
    report: () => request<Report>("/api/admin/reports", {}, token),
    exportCsv: () => request<Blob>("/api/admin/reports/export.csv", {}, token),
  };
}

export type AdminApi = ReturnType<typeof adminApi>;
