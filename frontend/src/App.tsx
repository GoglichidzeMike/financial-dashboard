import { FormEvent, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api } from "./lib/api";
import { DateFilter, LlmCheckResponse } from "./types/api";
import { Button } from "./components/ui/Button";
import { Card } from "./components/ui/Card";
import { StatusPill } from "./components/shared/StatusPill";
import { ChatDrawer, ChatHistoryItem } from "./components/chat/ChatDrawer";
import { TopNav } from "./components/navigation/TopNav";
import { DashboardPage } from "./pages/DashboardPage";
import { TransactionsPage } from "./pages/TransactionsPage";

const CHAT_SESSIONS_STORAGE_KEY = "finance_dashboard_chat_sessions";
const CHAT_ACTIVE_SESSION_STORAGE_KEY = "finance_dashboard_active_chat_session";

type ChatSession = {
  id: string;
  title: string;
  items: ChatHistoryItem[];
  createdAt: string;
  updatedAt: string;
};

function createNewSession(): ChatSession {
  const id = `chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const now = new Date().toISOString();
  return {
    id,
    title: "New Chat",
    items: [],
    createdAt: now,
    updatedAt: now,
  };
}

function App() {
  const [health, setHealth] = useState("loading");
  const [llmCheck, setLlmCheck] = useState<LlmCheckResponse | null>(null);
  const [checkingLlm, setCheckingLlm] = useState(false);

  const [dashboardFilters, setDashboardFilters] = useState<DateFilter>({
    dateFrom: "",
    dateTo: "",
  });

  const [chatQuestion, setChatQuestion] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatUseDashboardFilters, setChatUseDashboardFilters] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([createNewSession()]);
  const [activeChatSessionId, setActiveChatSessionId] = useState<string>("");

  useEffect(() => {
    api
      .getHealth()
      .then((res) => setHealth(res.status))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "unknown error";
        setHealth(`error: ${message}`);
      });
  }, []);

  useEffect(() => {
    try {
      const rawSessions = window.localStorage.getItem(CHAT_SESSIONS_STORAGE_KEY);
      const rawActive = window.localStorage.getItem(CHAT_ACTIVE_SESSION_STORAGE_KEY);
      if (rawSessions) {
        const parsed = JSON.parse(rawSessions) as ChatSession[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          setChatSessions(parsed);
          if (rawActive && parsed.some((session) => session.id === rawActive)) {
            setActiveChatSessionId(rawActive);
          } else {
            setActiveChatSessionId(parsed[0].id);
          }
          return;
        }
      }
    } catch {
      // no-op, fallback below
    }
    const first = createNewSession();
    setChatSessions([first]);
    setActiveChatSessionId(first.id);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(CHAT_SESSIONS_STORAGE_KEY, JSON.stringify(chatSessions));
  }, [chatSessions]);

  useEffect(() => {
    if (!activeChatSessionId) {
      return;
    }
    window.localStorage.setItem(CHAT_ACTIVE_SESSION_STORAGE_KEY, activeChatSessionId);
  }, [activeChatSessionId]);

  const onCheckLlm = async () => {
    setCheckingLlm(true);
    setLlmCheck(null);
    try {
      const result = await api.checkLlm();
      setLlmCheck(result);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setLlmCheck({
        configured: false,
        ok: false,
        model: "gpt-4o-mini",
        error: message,
      });
    } finally {
      setCheckingLlm(false);
    }
  };

  const onAskChat = async (event: FormEvent) => {
    event.preventDefault();
    const question = chatQuestion.trim();
    if (!question) {
      return;
    }

    setChatLoading(true);
    setChatError("");
    try {
      const activeSession = chatSessions.find((session) => session.id === activeChatSessionId);
      const historyForApi = (activeSession?.items ?? [])
        .slice(0, 10)
        .reverse()
        .map((item) => ({
          question: item.question,
          answer: item.response.answer,
        }));
      const response = await api.chat({
        question,
        date_from: chatUseDashboardFilters ? dashboardFilters.dateFrom || undefined : undefined,
        date_to: chatUseDashboardFilters ? dashboardFilters.dateTo || undefined : undefined,
        top_k: 20,
        history: historyForApi,
      });
      setChatSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeChatSessionId) {
            return session;
          }
          const createdAt = new Date().toLocaleString();
          const nextItems = [
            {
              id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
              question,
              response,
              createdAt,
            },
            ...session.items,
          ].slice(0, 80);
          const nextTitle =
            session.items.length === 0
              ? question.slice(0, 42) + (question.length > 42 ? "..." : "")
              : session.title;
          return {
            ...session,
            title: nextTitle || "Chat",
            items: nextItems,
            updatedAt: new Date().toISOString(),
          };
        })
      );
      setChatQuestion("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setChatError(message);
    } finally {
      setChatLoading(false);
    }
  };

  const onClearChatHistory = () => {
    setChatSessions((prev) =>
      prev.map((session) =>
        session.id === activeChatSessionId
          ? { ...session, items: [], title: "New Chat", updatedAt: new Date().toISOString() }
          : session
      )
    );
    setChatError("");
  };

  const onCreateChatSession = () => {
    const session = createNewSession();
    setChatSessions((prev) => [session, ...prev]);
    setActiveChatSessionId(session.id);
    setChatQuestion("");
    setChatError("");
  };

  const activeChatSession =
    chatSessions.find((session) => session.id === activeChatSessionId) ?? chatSessions[0];
  const chatHistory = activeChatSession?.items ?? [];
  const chatSessionsMeta = chatSessions
    .map((session) => ({
      id: session.id,
      title: session.title,
      updatedAt: session.updatedAt,
      messageCount: session.items.length,
    }))
    .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));

  const llmTone = useMemo(() => {
    if (!llmCheck) {
      return "neutral" as const;
    }
    return llmCheck.ok ? "ok" : "error";
  }, [llmCheck]);

  return (
    <>
      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        <Card className="border border-cyan-100 bg-gradient-to-r from-white to-cyan-50">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">
                Finance Dashboard
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                Health: <span className="font-semibold">{health}</span> | API: {api.baseUrl}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="secondary" onClick={onCheckLlm} disabled={checkingLlm}>
                {checkingLlm ? "Checking LLM..." : "Check LLM"}
              </Button>
              {llmCheck && (
                <StatusPill tone={llmTone} label={llmCheck.ok ? "LLM Ready" : "LLM Unavailable"} />
              )}
            </div>
          </div>
          {llmCheck && (
            <p className="mt-3 text-xs text-slate-500">
              Model: {llmCheck.model}
              {llmCheck.error ? ` | Error: ${llmCheck.error}` : ""}
              {llmCheck.response ? ` | Response: ${llmCheck.response}` : ""}
            </p>
          )}
          <div className="mt-4">
            <TopNav />
          </div>
        </Card>

        <Routes>
          <Route
            path="/dashboard"
            element={<DashboardPage onAppliedFiltersChange={setDashboardFilters} />}
          />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>

      <ChatDrawer
        isOpen={chatOpen}
        question={chatQuestion}
        loading={chatLoading}
        error={chatError}
        useDashboardFilters={chatUseDashboardFilters}
        history={chatHistory}
        sessions={chatSessionsMeta}
        activeSessionId={activeChatSession?.id ?? ""}
        onToggle={() => setChatOpen((prev) => !prev)}
        onQuestionChange={setChatQuestion}
        onToggleFilters={setChatUseDashboardFilters}
        onSubmit={onAskChat}
        onClearHistory={onClearChatHistory}
        onCreateSession={onCreateChatSession}
        onSelectSession={setActiveChatSessionId}
      />
    </>
  );
}

export default App;
