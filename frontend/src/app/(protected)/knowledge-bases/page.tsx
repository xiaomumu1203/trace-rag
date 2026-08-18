"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { kbApi } from "@/lib/api";
import type { KnowledgeBase } from "@/lib/types";

export default function KnowledgeBasesPage() {
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await kbApi.list();
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await kbApi.create({ name, description: description || undefined });
      setName("");
      setDescription("");
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("确定删除该知识库吗？关联文档、向量数据将被清除。")) return;
    try {
      await kbApi.delete(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">知识库</h1>
          <p className="mt-1 text-sm text-slate-500">管理你的 RAG 知识库</p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700"
        >
          + 新建知识库
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="mt-6 rounded-xl border border-slate-200 bg-white p-6"
        >
          <h2 className="mb-4 text-lg font-semibold text-slate-800">新建知识库</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                名称
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                placeholder="例如：产品文档"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                描述
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                placeholder="知识库描述（可选）"
              />
            </div>
          </div>
          <div className="mt-5 flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "创建中..." : "创建"}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              取消
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="mt-10 text-center text-slate-400">加载中...</div>
      ) : items.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-slate-300 p-12 text-center text-slate-400">
          还没有知识库，点击右上角创建第一个
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((kb) => (
            <div
              key={kb.id}
              className="group rounded-xl border border-slate-200 bg-white p-5 transition hover:shadow-md"
            >
              <Link href={`/knowledge-bases/${kb.id}`}>
                <h3 className="text-lg font-semibold text-slate-800 group-hover:text-brand-600">
                  {kb.name}
                </h3>
              </Link>
              <p className="mt-1 line-clamp-2 text-sm text-slate-500">
                {kb.description || "暂无描述"}
              </p>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  ID: {kb.id}
                </span>
                <div className="flex gap-2">
                  <Link
                    href={`/knowledge-bases/${kb.id}`}
                    className="rounded-md bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600 hover:bg-brand-100"
                  >
                    进入
                  </Link>
                  <button
                    onClick={() => handleDelete(kb.id)}
                    className="rounded-md bg-red-50 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
