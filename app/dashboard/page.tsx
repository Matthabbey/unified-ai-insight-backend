"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  getToken, getUser, clearToken,
  getStats, getAlerts, getKnowledgeGaps, acknowledgeAlert,
  askStream,
  type DashboardStats, type Alert, type KnowledgeGap,
  type SSEEvent, type AgentAction, type Citation,
} from "@/app/lib/api";

// ── Agent colour palette ──────────────────────────────────────────────────────
const AGENT_COLOURS: Record<string, string> = {
  Strategist: "bg-purple-100 text-purple-800 border-purple-200",
  Researcher:  "bg-blue-100 text-blue-800 border-blue-200",
  Analyst:     "bg-green-100 text-green-800 border-green-200",
  Watchdog:    "bg-orange-100 text-orange-800 border-orange-200",
  Scribe:      "bg-pink-100 text-pink-800 border-pink-200",
};

function agentColour(name: string) {
  return AGENT_COLOURS[name] ?? "bg-zinc-100 text-zinc-800 border-zinc-200";
}

// ── Severity helpers ───────────────────────────────────────────────────────────
function severityBadge(s: string) {
  if (s === "critical") return "bg-red-100 text-red-700 border-red-200";
  if (s === "warning")  return "bg-yellow-100 text-yellow-700 border-yellow-200";
  return "bg-blue-100 text-blue-700 border-blue-200";
}

// ── Stat card ──────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-5 ${accent ? "bg-[#FFCC00] border-yellow-300" : "bg-white border-zinc-200"}`}>
      <p className={`text-xs font-medium uppercase tracking-wide ${accent ? "text-black/60" : "text-zinc-500"}`}>
        {label}
      </p>
      <p className={`text-3xl font-bold mt-1 ${accent ? "text-black" : "text-zinc-900"}`}>
        {value}
      </p>
      {sub && <p className={`text-xs mt-1 ${accent ? "text-black/50" : "text-zinc-400"}`}>{sub}</p>}
    </div>
  );
}

// ── Suggested queries ──────────────────────────────────────────────────────────
const SUGGESTED = [
  "Why are customer complaints spiking in Lagos?",
  "Which vendor contracts are expiring soon?",
  "What is our current NCC compliance status?",
  "What are the key findings from the Q1 2026 network report?",
];

// ── Main component ─────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();

  // Auth
  const [user, setUser] = useState<Record<string, unknown> | null>(null);

  // Data
  const [stats, setStats]   = useState<DashboardStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [gaps, setGaps]     = useState<KnowledgeGap[]>([]);

  // Chat state
  const [query, setQuery]               = useState("");
  const [streaming, setStreaming]       = useState(false);
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [traceEvents, setTraceEvents]   = useState<AgentAction[]>([]);
  const [citations, setCitations]       = useState<Citation[]>([]);
  const [followups, setFollowups]       = useState<string[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; trace?: AgentAction[]; citations?: Citation[] }[]>([]);
  const [currentStatus, setCurrentStatus] = useState("");

  const abortRef   = useRef<AbortController | null>(null);
  const chatBottom = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLInputElement>(null);

  // ── Auth check ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/login"); return; }
    setUser(getUser());
    loadDashboard();
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── Scroll chat to bottom ─────────────────────────────────────────────────
  useEffect(() => {
    chatBottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamedAnswer]);

  // ── Load dashboard data ────────────────────────────────────────────────────
  async function loadDashboard() {
    try {
      const [s, a, g] = await Promise.all([
        getStats().catch(() => null),
        getAlerts("new", 8).catch(() => ({ alerts: [], total: 0, critical_count: 0, warning_count: 0 })),
        getKnowledgeGaps(5).catch(() => ({ gaps: [], total: 0 })),
      ]);
      if (s) setStats(s);
      setAlerts(a.alerts);
      setGaps(g.gaps);
    } catch {
      // non-fatal — dashboard still usable
    }
  }

  // ── Chat submit ────────────────────────────────────────────────────────────
  const handleAsk = useCallback(async (q: string) => {
    if (!q.trim() || streaming) return;

    abortRef.current = new AbortController();

    setMessages(prev => [...prev, { role: "user", content: q }]);
    setQuery("");
    setStreamedAnswer("");
    setTraceEvents([]);
    setCitations([]);
    setFollowups([]);
    setStreaming(true);
    setCurrentStatus("Atlas is thinking…");

    let finalAnswer = "";
    const runTrace: AgentAction[] = [];

    try {
      await askStream(
        q,
        conversationId,
        (event: SSEEvent) => {
          switch (event.type) {
            case "start":
              setCurrentStatus(event.message);
              break;

            case "agent_action":
              runTrace.push({ agent: event.agent, tool: event.tool, description: event.description, timestamp: event.timestamp });
              setTraceEvents([...runTrace]);
              setCurrentStatus(`${event.agent} → ${event.tool}`);
              break;

            case "token":
              finalAnswer += event.content;
              setStreamedAnswer(finalAnswer);
              break;

            case "complete":
              finalAnswer = event.answer;
              setStreamedAnswer(finalAnswer);
              setCitations(event.citations ?? []);
              setFollowups(event.suggested_followups ?? []);
              setCurrentStatus("");
              setMessages(prev => [
                ...prev,
                {
                  role: "assistant",
                  content: event.answer,
                  trace: runTrace,
                  citations: event.citations ?? [],
                },
              ]);
              setStreamedAnswer("");
              setTraceEvents([]);
              break;

            case "error":
              setCurrentStatus(`Error: ${event.message}`);
              break;
          }
        },
        abortRef.current.signal
      );
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        setCurrentStatus(`Failed: ${(err as Error).message}`);
      }
    } finally {
      setStreaming(false);
    }
  }, [streaming, conversationId]);

  function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    handleAsk(query);
  }

  function stopStream() {
    abortRef.current?.abort();
    setStreaming(false);
    setCurrentStatus("");
  }

  function logout() {
    clearToken();
    router.push("/login");
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col">

      {/* Header */}
      <header className="bg-black text-white px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#FFCC00] flex items-center justify-center font-black text-black text-sm">A</div>
          <span className="font-bold text-lg tracking-tight">MTN Atlas</span>
          <span className="hidden sm:block text-zinc-500 text-xs border-l border-zinc-700 pl-3">
            Enterprise Document Intelligence
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-zinc-400 text-sm hidden sm:block">
            {user?.full_name as string || user?.email as string || "User"}
          </span>
          <button
            onClick={loadDashboard}
            className="text-zinc-400 hover:text-white text-xs transition-colors"
          >
            Refresh
          </button>
          <button
            onClick={logout}
            className="bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 rounded-lg text-xs transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Stats bar */}
      {stats && (
        <div className="bg-white border-b border-zinc-200 px-6 py-4">
          <div className="max-w-7xl mx-auto grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
            <StatCard label="Documents" value={stats.documents_indexed} sub={`${stats.total_documents} total`} />
            <StatCard label="Queries today" value={stats.total_queries_today} sub={`${stats.total_queries_this_week} this week`} />
            <StatCard label="Active alerts" value={stats.active_alerts} sub={`${stats.critical_alerts} critical`} accent={stats.critical_alerts > 0} />
            <StatCard label="Avg response" value={`${Math.round(stats.avg_query_response_ms)}ms`} />
            <StatCard label="Knowledge gaps" value={gaps.length} sub="unanswered queries" />
            <StatCard label="System" value="Online" sub="All services healthy" />
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 grid grid-cols-1 lg:grid-cols-5 gap-6 min-h-0">

        {/* ── Left: Chat panel ───────────────────────────────────────────── */}
        <div className="lg:col-span-3 flex flex-col bg-white rounded-2xl border border-zinc-200 overflow-hidden min-h-[600px]">

          {/* Chat header */}
          <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-zinc-900">Ask Atlas</h2>
              <p className="text-xs text-zinc-500 mt-0.5">Multi-agent document intelligence</p>
            </div>
            {streaming && (
              <button onClick={stopStream} className="text-xs text-red-500 hover:text-red-700 border border-red-200 rounded-lg px-3 py-1.5 transition-colors">
                Stop
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center gap-6 text-center py-10">
                <div className="w-16 h-16 rounded-2xl bg-[#FFCC00]/20 flex items-center justify-center">
                  <span className="text-3xl">🔍</span>
                </div>
                <div>
                  <p className="text-zinc-700 font-medium">Ask any question about MTN&apos;s documents</p>
                  <p className="text-zinc-400 text-sm mt-1">Contracts, complaints, compliance, network reports</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
                  {SUGGESTED.map((s) => (
                    <button
                      key={s}
                      onClick={() => handleAsk(s)}
                      className="text-left text-sm bg-zinc-50 hover:bg-[#FFCC00]/10 border border-zinc-200 hover:border-yellow-300 rounded-xl px-4 py-3 text-zinc-700 transition-colors leading-snug"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-black text-white rounded-br-sm"
                    : "bg-zinc-100 text-zinc-900 rounded-bl-sm"
                }`}>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                  {/* Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-zinc-200/50 space-y-1">
                      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Sources</p>
                      {msg.citations.map((c, ci) => (
                        <div key={ci} className="text-xs bg-white/60 rounded-lg px-3 py-2">
                          <p className="font-medium text-zinc-700 truncate">{c.document_title}</p>
                          <p className="text-zinc-500 mt-0.5 line-clamp-2">{c.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Follow-ups (last assistant message only) */}
                  {msg.role === "assistant" && i === messages.length - 1 && followups.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-zinc-200/50 space-y-1.5">
                      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Suggested follow-ups</p>
                      {followups.map((f, fi) => (
                        <button
                          key={fi}
                          onClick={() => handleAsk(f)}
                          className="block w-full text-left text-xs bg-white hover:bg-yellow-50 border border-zinc-200 hover:border-yellow-300 rounded-lg px-3 py-2 text-zinc-700 transition-colors"
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* In-progress streaming answer */}
            {streaming && (
              <div className="flex justify-start">
                <div className="max-w-[85%] bg-zinc-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  {streamedAnswer ? (
                    <p className="text-sm text-zinc-900 leading-relaxed whitespace-pre-wrap">
                      {streamedAnswer}
                      <span className="inline-block w-2 h-4 bg-zinc-400 ml-0.5 animate-pulse rounded-sm" />
                    </p>
                  ) : (
                    <div className="flex items-center gap-2 text-zinc-500 text-sm">
                      <div className="flex gap-1">
                        {[0,1,2].map(i => (
                          <div key={i} className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                        ))}
                      </div>
                      <span>{currentStatus}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            <div ref={chatBottom} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-zinc-100 bg-white">
            <form onSubmit={handleFormSubmit} className="flex gap-3">
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={streaming}
                placeholder="Ask about contracts, complaints, compliance, network performance…"
                className="flex-1 bg-zinc-50 border border-zinc-200 rounded-xl px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:border-[#FFCC00] focus:bg-white transition-colors disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={streaming || !query.trim()}
                className="bg-[#FFCC00] hover:bg-yellow-300 disabled:opacity-40 disabled:cursor-not-allowed text-black font-semibold px-5 rounded-xl transition-colors text-sm flex-shrink-0"
              >
                Ask
              </button>
            </form>
          </div>
        </div>

        {/* ── Right: Live trace + Alerts + Gaps ─────────────────────────── */}
        <div className="lg:col-span-2 flex flex-col gap-4 min-h-0">

          {/* Agent Trace */}
          <div className="bg-white rounded-2xl border border-zinc-200 flex flex-col max-h-72">
            <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-zinc-900 text-sm">Agent Trace</h3>
                {streaming && (
                  <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                    Live
                  </span>
                )}
              </div>
              {currentStatus && streaming && (
                <span className="text-xs text-zinc-400 truncate max-w-[120px]">{currentStatus}</span>
              )}
            </div>
            <div className="overflow-y-auto p-3 space-y-2 flex-1">
              {traceEvents.length === 0 && !streaming ? (
                <p className="text-xs text-zinc-400 text-center py-4">
                  Agent activity will appear here during a query
                </p>
              ) : (
                traceEvents.map((ev, i) => (
                  <div
                    key={i}
                    className={`flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-xs ${agentColour(ev.agent)}`}
                  >
                    <span className="font-semibold flex-shrink-0">{ev.agent}</span>
                    <span className="text-current/70 flex-shrink-0">→</span>
                    <span className="font-medium flex-shrink-0">{ev.tool}</span>
                    <span className="text-current/60 truncate leading-relaxed">{ev.description}</span>
                  </div>
                ))
              )}
              {streaming && traceEvents.length > 0 && (
                <div className="flex items-center gap-2 px-3 py-2 text-xs text-zinc-400">
                  <div className="flex gap-1">
                    {[0,1,2].map(i => <div key={i} className="w-1 h-1 bg-zinc-300 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />)}
                  </div>
                  Working…
                </div>
              )}
            </div>
          </div>

          {/* Active Alerts */}
          <div className="bg-white rounded-2xl border border-zinc-200 flex flex-col flex-1 min-h-0 max-h-80">
            <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between flex-shrink-0">
              <h3 className="font-semibold text-zinc-900 text-sm">Active Alerts</h3>
              {alerts.filter(a => a.severity === "critical").length > 0 && (
                <span className="text-xs bg-red-100 text-red-700 border border-red-200 rounded-full px-2 py-0.5">
                  {alerts.filter(a => a.severity === "critical").length} critical
                </span>
              )}
            </div>
            <div className="overflow-y-auto p-3 space-y-2 flex-1">
              {alerts.length === 0 ? (
                <p className="text-xs text-zinc-400 text-center py-6">No active alerts</p>
              ) : (
                alerts.map((alert) => (
                  <div key={alert.id} className="rounded-xl border border-zinc-100 p-3 hover:border-zinc-200 transition-colors">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className={`text-xs border rounded-full px-2 py-0.5 font-medium ${severityBadge(alert.severity)}`}>
                            {alert.severity}
                          </span>
                        </div>
                        <p className="text-xs font-medium text-zinc-800 leading-snug">{alert.title}</p>
                        <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2 leading-relaxed">{alert.summary}</p>
                      </div>
                      <button
                        onClick={async () => {
                          await acknowledgeAlert(alert.id).catch(() => {});
                          setAlerts(prev => prev.filter(a => a.id !== alert.id));
                        }}
                        className="text-xs text-zinc-400 hover:text-zinc-700 flex-shrink-0 transition-colors"
                        title="Acknowledge"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Knowledge Gaps */}
          {gaps.length > 0 && (
            <div className="bg-white rounded-2xl border border-amber-200 flex flex-col max-h-56">
              <div className="px-5 py-3 border-b border-amber-100 flex items-center gap-2 flex-shrink-0">
                <span className="text-sm">⚠️</span>
                <h3 className="font-semibold text-amber-900 text-sm">Knowledge Gaps</h3>
                <span className="ml-auto text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
                  {gaps.length} detected
                </span>
              </div>
              <div className="overflow-y-auto p-3 space-y-1.5 flex-1">
                {gaps.map((gap) => (
                  <div key={gap.id} className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">
                    <p className="text-xs text-amber-900 leading-snug line-clamp-2">{gap.query}</p>
                    <p className="text-xs text-amber-500 mt-0.5">
                      Confidence: {(gap.confidence_score * 100).toFixed(0)}% — upload relevant documents
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
