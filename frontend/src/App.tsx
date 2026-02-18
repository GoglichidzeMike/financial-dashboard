import { FormEvent, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api } from "./lib/api";
import {
  ChatMessage,
  ChatThread,
  DateFilter,
  LlmCheckResponse,
} from "./types/api";
import { Button } from "./components/ui/Button";
import { Card } from "./components/ui/Card";
import { StatusPill } from "./components/shared/StatusPill";
import { ChatDrawer, ChatHistoryItem } from "./components/chat/ChatDrawer";
import { TopNav } from "./components/navigation/TopNav";
import { DashboardPage } from "./pages/DashboardPage";
import { TransactionsPage } from "./pages/TransactionsPage";

function mapMessagesToHistory(messages: ChatMessage[]): ChatHistoryItem[] {
  const items: ChatHistoryItem[] = [];
  for (const message of messages) {
    if (message.role !== "assistant" || !message.answer_text) {
      continue;
    }
    items.push({
      id: message.id,
      question: message.question_text || "Question",
      response: {
        thread_id: "",
        message_id: message.id,
        mode: message.mode || "sql",
        answer: message.answer_text,
        sources: message.sources || [],
      },
      createdAt: new Date(message.created_at).toLocaleString(),
    });
  }
  return items.reverse();
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

  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string>("");
  const [threadMessages, setThreadMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    api
      .getHealth()
      .then((res) => setHealth(res.status))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "unknown error";
        setHealth(`error: ${message}`);
      });
  }, []);

  const refreshThreads = async (preferredThreadId?: string) => {
    const response = await api.listChatThreads("active");
    let nextThreads: ChatThread[] = response.items;
    if (nextThreads.length === 0) {
      const created = await api.createChatThread({ title: "New Chat" });
      nextThreads = [{ ...created, message_count: 0 }];
    }
    setThreads(nextThreads);
    const selected =
      (preferredThreadId && nextThreads.find((thread) => thread.id === preferredThreadId)?.id) ||
      nextThreads[0].id;
    setActiveThreadId(selected);
  };

  useEffect(() => {
    refreshThreads().catch((err: unknown) => {
      const message = err instanceof Error ? err.message : "unknown error";
      setChatError(message);
    });
  }, []);

  useEffect(() => {
    if (!activeThreadId) {
      return;
    }
    api
      .listChatMessages(activeThreadId, 200)
      .then((res) => setThreadMessages(res.items))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "unknown error";
        setChatError(message);
      });
  }, [activeThreadId]);

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
    if (!question || !activeThreadId) {
      return;
    }

    setChatLoading(true);
    setChatError("");
    try {
      await api.chat({
        thread_id: activeThreadId,
        question,
        date_from: chatUseDashboardFilters ? dashboardFilters.dateFrom || undefined : undefined,
        date_to: chatUseDashboardFilters ? dashboardFilters.dateTo || undefined : undefined,
        top_k: 20,
      });
      setChatQuestion("");
      await Promise.all([
        refreshThreads(activeThreadId),
        api.listChatMessages(activeThreadId, 200).then((res) => setThreadMessages(res.items)),
      ]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setChatError(message);
    } finally {
      setChatLoading(false);
    }
  };

  const onCreateChatSession = async () => {
    try {
      const thread = await api.createChatThread({ title: "New Chat" });
      await refreshThreads(thread.id);
      setThreadMessages([]);
      setChatQuestion("");
      setChatError("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setChatError(message);
    }
  };

  const onClearChatHistory = async () => {
    if (!activeThreadId) {
      return;
    }
    try {
      await api.deleteChatThread(activeThreadId);
      await refreshThreads();
      setThreadMessages([]);
      setChatError("");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "unknown error";
      setChatError(message);
    }
  };

  const chatHistory = useMemo(() => mapMessagesToHistory(threadMessages), [threadMessages]);

  const chatSessionsMeta = useMemo(
    () =>
      threads.map((thread) => ({
        id: thread.id,
        title: thread.title,
        updatedAt: thread.updated_at,
        messageCount: thread.message_count,
      })),
    [threads]
  );

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
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">Finance Dashboard</h1>
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
        activeSessionId={activeThreadId}
        onToggle={() => setChatOpen((prev) => !prev)}
        onQuestionChange={setChatQuestion}
        onToggleFilters={setChatUseDashboardFilters}
        onSubmit={onAskChat}
        onClearHistory={onClearChatHistory}
        onCreateSession={onCreateChatSession}
        onSelectSession={setActiveThreadId}
      />
    </>
  );
}

export default App;
