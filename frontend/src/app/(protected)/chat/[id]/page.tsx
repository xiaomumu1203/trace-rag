"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useParams } from "next/navigation";
import { useStreamingChat } from "@/hooks/useStreamingChat";
import { chatApi } from "@/lib/api";
import type { CitationSource } from "@/lib/types";

export default function ChatConversationPage() {
  const { id } = useParams<{ id: string }>();
  const chatId = Number(id);
  const { messages, isLoading, error, send, load, reset } = useStreamingChat();
  const [input, setInput] = useState("");
  const [chatTitle, setChatTitle] = useState("");
  const [selectedSource, setSelectedSource] = useState<CitationSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!Number.isInteger(chatId) || chatId <= 0) return;
    let cancelled = false;
    reset();
    void load(chatId);
    void chatApi.get(chatId).then((chat) => {
      if (!cancelled) setChatTitle(chat.title);
    }).catch(() => {
      if (!cancelled) setChatTitle("");
    });

    return () => {
      cancelled = true;
    };
  }, [chatId, load, reset]);

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    await send(chatId, text);
  }

  function renderAssistantContent(content: string, sources: CitationSource[] = []) {
    const citationPattern = /\[citation:(\d+)\]/g;
    const elements: ReactNode[] = [];
    let cursor = 0;

    for (const match of content.matchAll(citationPattern)) {
      const [citation, indexText] = match;
      const index = Number(indexText);
      const source = sources.find((item) => item.index === index);
      elements.push(content.slice(cursor, match.index));
      elements.push(
        <button
          key={`${citation}-${match.index}`}
          type="button"
          onClick={() => source && setSelectedSource(source)}
          disabled={!source}
          title={source ? "查看引用来源" : "该引用来源不可用"}
          className="mx-0.5 inline-flex align-super text-xs font-semibold text-brand-600 underline decoration-brand-300 underline-offset-2 hover:text-brand-800 disabled:cursor-default disabled:text-slate-400"
        >
          [{index}]
        </button>
      );
      cursor = (match.index ?? 0) + citation.length;
    }
    elements.push(content.slice(cursor));
    return elements;
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <h1 className="text-xl font-bold text-slate-800">
          {chatTitle || `对话 #${chatId}`}
        </h1>
        <span className="text-xs text-slate-400">支持基于知识库的流式回答</span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto py-6">
        {messages.length === 0 && (
          <div className="py-16 text-center text-slate-400">
            开始对话吧，AI 会结合你的知识库回答
          </div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={idx}
              className={`flex ${isUser ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`flex max-w-[80%] flex-col gap-2 ${isUser ? "items-end" : "items-start"}`}
              >
                <div className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  isUser
                    ? "rounded-br-sm bg-brand-600 text-white"
                    : "rounded-bl-sm border border-slate-200 bg-white text-slate-800"
                }`}
              >
                {isUser
                  ? msg.content
                  : msg.content
                    ? renderAssistantContent(msg.content, msg.sources)
                    : isLoading && idx === messages.length - 1
                      ? "思考中..."
                      : ""}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="mb-3 rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {selectedSource && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={`引用来源 ${selectedSource.index}`}
          onClick={() => setSelectedSource(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-slate-800">引用来源 [{selectedSource.index}]</h2>
                <p className="mt-1 text-sm text-slate-500">
                  知识库：{selectedSource.knowledge_base_name || `ID ${String(selectedSource.metadata.kb_id ?? "未知")}`}
                </p>
                {selectedSource.file_name && <p className="text-sm text-slate-500">文件：{selectedSource.file_name}</p>}
              </div>
              <button
                type="button"
                onClick={() => setSelectedSource(null)}
                className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              >
                关闭
              </button>
            </div>
            <pre className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm leading-6 text-slate-700">
              {selectedSource.page_content}
            </pre>
          </div>
        </div>
      )}

      <form onSubmit={handleSend} className="flex gap-3 border-t border-slate-200 pt-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
          placeholder="输入你的问题..."
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-brand-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
        >
          {isLoading ? "生成中..." : "发送"}
        </button>
      </form>
    </div>
  );
}
