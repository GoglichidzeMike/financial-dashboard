import { FormEvent, useState } from "react";

import { ChatResponse } from "../../types/api";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { StatusPill } from "../shared/StatusPill";
import { MarkdownLite } from "./MarkdownLite";
import { ChatTable } from "./ChatTable";

export type ChatHistoryItem = {
  id: string;
  question: string;
  response: ChatResponse;
  createdAt: string;
};

export type ChatSessionMeta = {
  id: string;
  title: string;
  updatedAt: string;
  messageCount: number;
};

type ChatDrawerProps = {
  isOpen: boolean;
  question: string;
  loading: boolean;
  error: string;
  useDashboardFilters: boolean;
  history: ChatHistoryItem[];
  sessions: ChatSessionMeta[];
  activeSessionId: string;
  onToggle: () => void;
  onQuestionChange: (value: string) => void;
  onToggleFilters: (checked: boolean) => void;
  onSubmit: (event: FormEvent) => void;
  onClearHistory: () => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: string) => void;
};

export function ChatDrawer({
  isOpen,
  question,
  loading,
  error,
  useDashboardFilters,
  history,
  sessions,
  activeSessionId,
  onToggle,
  onQuestionChange,
  onToggleFilters,
  onSubmit,
  onClearHistory,
  onCreateSession,
  onSelectSession,
}: ChatDrawerProps) {
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});

  const toggleSource = (key: string) => {
    setExpandedSources((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <>
      <button
        type="button"
        onClick={onToggle}
        className="fixed bottom-6 right-6 z-40 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-cyan-700"
      >
        {isOpen ? "Close Chat" : "Open Chat"}
      </button>

      <aside
        className={`fixed right-0 top-0 z-30 h-full w-full max-w-xl border-l border-slate-200 bg-white shadow-2xl transition-transform duration-300 ${isOpen ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex h-full flex-col">
          <header className="border-b border-slate-200 px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                  Chat Assistant
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  Ask anytime. History is persisted on server.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" className="h-8 px-3 text-xs" onClick={onCreateSession}>
                  New Chat
                </Button>
                <Button variant="ghost" className="h-8 px-3 text-xs" onClick={onClearHistory}>
                  Clear
                </Button>
              </div>
            </div>
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {sessions.map((session) => {
                const isActive = session.id === activeSessionId;
                return (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    className={`rounded-lg border px-3 py-1.5 text-left text-xs transition ${isActive ? "border-cyan-300 bg-cyan-50 text-cyan-800" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
                  >
                    <p className="font-semibold">{session.title}</p>
                    <p className="text-[10px] opacity-80">{session.messageCount} msgs</p>
                  </button>
                );
              })}
            </div>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {history.length === 0 && (
              <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
                No messages yet. Try: "Compare January 2026 vs February 2026".
              </p>
            )}

            {history.map((item) => (
              <div key={item.id} className="space-y-2">
                <div className="rounded-xl border border-cyan-100 bg-cyan-50 p-3">
                  <p className="text-xs uppercase tracking-wide text-cyan-700">You</p>
                  <p className="mt-1 text-sm text-slate-800">{item.question}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  {(() => {
                    const primaryTableSource = item.response.sources.find(
                      (source) =>
                        source.table_columns &&
                        source.table_rows &&
                        source.table_columns.length > 0 &&
                        source.table_rows.length > 0
                    );
                    return (
                      <>
                  <div className="mb-2 flex items-center gap-2">
                    <StatusPill tone="neutral" label={`mode: ${item.response.mode}`} />
                    <span className="text-[11px] text-slate-500">{item.createdAt}</span>
                  </div>
                  <MarkdownLite content={item.response.answer} />
                  {primaryTableSource && (
                    <div className="mt-3">
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                        {primaryTableSource.title}
                      </p>
                      <ChatTable
                        columns={primaryTableSource.table_columns ?? []}
                        rows={primaryTableSource.table_rows ?? []}
                      />
                    </div>
                  )}
                  {item.response.sources.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {item.response.sources.map((source, index) => (
                        (() => {
                          const sourceKey = `${item.id}-${source.title}-${index}`;
                          const hasTable =
                            Boolean(source.table_columns) &&
                            Boolean(source.table_rows) &&
                            (source.table_rows?.length ?? 0) > 0;
                          const isExpanded =
                            expandedSources[sourceKey] ?? hasTable;

                          return (
                            <div
                              key={sourceKey}
                              className="rounded-lg border border-slate-200 bg-white p-2"
                            >
                              <button
                                type="button"
                                className="flex w-full items-center justify-between gap-3 text-left"
                                onClick={() => toggleSource(sourceKey)}
                              >
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                  {source.title} ({source.source_type})
                                </p>
                                <span className="text-[11px] font-semibold text-cyan-700">
                                  {isExpanded ? "Hide" : "Show"}
                                </span>
                              </button>
                              {isExpanded && (
                                <div className="mt-1">
                                  <MarkdownLite
                                    content={source.content}
                                    className="text-xs leading-5"
                                  />
                                  {source.table_columns &&
                                    source.table_rows &&
                                    source.table_columns.length > 0 &&
                                    source.table_rows.length > 0 && (
                                      <ChatTable
                                        columns={source.table_columns}
                                        rows={source.table_rows}
                                      />
                                    )}
                                </div>
                              )}
                            </div>
                          );
                        })()
                      ))}
                    </div>
                  )}
                      </>
                    );
                  })()}
                </div>
              </div>
            ))}
          </div>

          <footer className="border-t border-slate-200 px-4 py-3">
            <form className="space-y-2" onSubmit={onSubmit}>
              <Input
                className="w-full"
                type="text"
                placeholder="Ask about spending, merchants, categories..."
                value={question}
                onChange={(e) => onQuestionChange(e.target.value)}
              />
              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                  <input
                    type="checkbox"
                    checked={useDashboardFilters}
                    onChange={(e) => onToggleFilters(e.target.checked)}
                  />
                  Use dashboard date filters
                </label>
                <Button type="submit" disabled={loading || !question.trim()}>
                  {loading ? "Thinking..." : "Ask"}
                </Button>
              </div>
              {error && <p className="text-xs text-rose-600">Chat error: {error}</p>}
            </form>
          </footer>
        </div>
      </aside>
    </>
  );
}
