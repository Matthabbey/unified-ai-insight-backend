// Atlas API client — all requests proxy through Next.js rewrites to FastAPI
// at http://localhost:8000 (configured in next.config.ts)

const BASE = "";  // rewrites handle the proxy; use relative paths

// ── Token helpers ──────────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("atlas_token");
}

export function setToken(token: string): void {
  localStorage.setItem("atlas_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("atlas_token");
}

export function getUser(): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("atlas_user");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function setUser(user: Record<string, unknown>): void {
  localStorage.setItem("atlas_user", JSON.stringify(user));
}

// ── Base fetch ────────────────────────────────────────────────────────────────

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorised");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  const data = await apiFetch<{ access_token: string; user: Record<string, unknown> }>(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) }
  );
  setToken(data.access_token);
  setUser(data.user);
  return data;
}

// ── SSE Streaming ─────────────────────────────────────────────────────────────

export type SSEEvent =
  | { type: "start"; message: string; timestamp: string }
  | { type: "agent_action"; agent: string; tool: string; description: string; timestamp: string }
  | { type: "token"; content: string }
  | { type: "complete"; answer: string; citations: Citation[]; suggested_followups: string[]; agent_trace: AgentAction[]; duration_ms: number }
  | { type: "error"; message: string };

export interface Citation {
  document_id: string;
  document_title: string;
  excerpt: string;
  relevance_score?: number;
}

export interface AgentAction {
  agent: string;
  tool: string;
  description: string;
  timestamp: string;
}

export async function askStream(
  query: string,
  conversationId: string | null,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const token = getToken();
  const res = await fetch("/api/atlas/ask/stream-http", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, conversation_id: conversationId }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Stream failed: HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";  // keep incomplete line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data: ")) continue;
      const payload = trimmed.slice(6);
      if (payload === "[DONE]") return;
      try {
        onEvent(JSON.parse(payload) as SSEEvent);
      } catch {
        // skip malformed event
      }
    }
  }
}

// ── Stats & Alerts ────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_documents: number;
  documents_indexed: number;
  total_queries_today: number;
  total_queries_this_week: number;
  active_alerts: number;
  critical_alerts: number;
  avg_query_response_ms: number;
}

export async function getStats(): Promise<DashboardStats> {
  return apiFetch("/api/analytics/stats");
}

export interface Alert {
  id: string;
  title: string;
  summary: string;
  severity: "critical" | "warning" | "info";
  status: string;
  alert_type: string;
  created_at: string;
}

export interface AlertList {
  alerts: Alert[];
  total: number;
  critical_count: number;
  warning_count: number;
}

export async function getAlerts(status = "new", limit = 10): Promise<AlertList> {
  return apiFetch(`/api/alerts?status=${status}&limit=${limit}`);
}

export async function acknowledgeAlert(id: string): Promise<void> {
  await apiFetch(`/api/alerts/${id}/acknowledge`, { method: "PATCH" });
}

export interface KnowledgeGap {
  id: string;
  query: string;
  confidence_score: number;
  created_at: string;
}

export async function getKnowledgeGaps(limit = 10): Promise<{ gaps: KnowledgeGap[]; total: number }> {
  return apiFetch(`/api/analytics/knowledge-gaps?limit=${limit}`);
}

export async function getDailyBriefing(
): Promise<Record<string, unknown>> {
  return apiFetch("/api/atlas/briefing", { method: "POST" });
}
