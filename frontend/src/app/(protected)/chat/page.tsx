"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { chatApi, kbApi } from "@/lib/api";
import type { Chat, KnowledgeBase } from "@/lib/types";

export default function ChatListPage() {
  const router = useRouter();
  const [chats, setChats] = useState<Chat[]>([]);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [title, setTitle] = useState("");
  const [selectedKbs, setSelectedKbs] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, k] = await Promise.all([chatApi.list(), kbApi.list()]);
      setChats(c);
      setKbs(k);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function toggleKb(id: number) {
    setSelectedKbs((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (selectedKbs.length === 0) {
      alert("请至少选择一个知识库");
      return;
    }
    setSubmitting(true);
    try {
      const chat = await chatApi.create({
        title: title.trim() || "新对话",
        chat_knowledge_base_ids: selectedKbs,
      });
      router.push(`/chat/${chat.id}`);
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("确定删除该聊天记录？")) return;
    try {
      await chatApi.delete(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">聊天</h1>
          <p className="mt-1 text-sm text-slate-500">基于知识库的智能对话</p>
        </div>
        <button
          onClick={() => setShowNew((v) => !v)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
        >
          + 新建对话
        </button>
      </div>

      {showNew && (
        <form
          onSubmit={handleCreate}
          className="mt-6 rounded-xl border border-slate-200 bg-white p-6"
        >
          <h2 className="mb-4 text-lg font-semibold text-slate-800">新建对话</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                标题
              </label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                placeholder="例如：产品问题咨询"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                关联知识库（可多选）
              </label>
              {kbs.length === 0 ? (
                <p className="mt-1 text-sm text-slate-400">
                  暂无知识库，请先创建
                </p>
              ) : (
                <div className="mt-2 flex flex-wrap gap-2">
                  {kbs.map((kb) => (
                    <button
                      key={kb.id}
                      type="button"
                      onClick={() => toggleKb(kb.id)}
                      className={`rounded-full px-3 py-1 text-sm transition ${
                        selectedKbs.includes(kb.id)
                          ? "bg-brand-600 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {kb.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="mt-5 flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "创建中..." : "创建并进入"}
            </button>
            <button
              type="button"
              onClick={() => setShowNew(false)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              取消
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="mt-10 text-center text-slate-400">加载中...</div>
      ) : chats.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-slate-300 p-12 text-center text-slate-400">
          还没有对话，点击右上角新建一个
        </div>
      ) : (
        <div className="mt-6 space-y-3">
          {chats.map((chat) => (
            <div
              key={chat.id}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4 transition hover:shadow-sm"
            >
              <button
                onClick={() => router.push(`/chat/${chat.id}`)}
                className="min-w-0 flex-1 text-left"
              >
                <div className="truncate font-medium text-slate-800">
                  {chat.title}
                </div>
                <div className="mt-0.5 text-xs text-slate-400">
                  ID: {chat.id} · 关联知识库:{" "}
                  {chat.chat_knowledge_base_ids?.join(", ") || "无"}
                </div>
              </button>
              <button
                onClick={() => handleDelete(chat.id)}
                className="ml-3 rounded-md bg-red-50 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
              >
                删除
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
