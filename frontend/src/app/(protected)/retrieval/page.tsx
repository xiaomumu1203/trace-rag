"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { kbApi } from "@/lib/api";
import type { KnowledgeBase, RetrievalItem } from "@/lib/types";

export default function RetrievalPage() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [kbId, setKbId] = useState<number | "">("");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<RetrievalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setKbs(await kbApi.list());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!kbId) {
      alert("请先选择知识库");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await kbApi.testRetrieval({
        query,
        kb_id: Number(kbId),
        top_k: topK,
      });
      setResults(res.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "检索失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">检索测试</h1>
        <p className="mt-1 text-sm text-slate-500">
          查看向量检索与 BM25 检索经 RRF 融合后的排序结果
        </p>
      </div>

      <form
        onSubmit={handleSearch}
        className="mt-6 rounded-xl border border-slate-200 bg-white p-6"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="md:col-span-1">
            <label className="block text-sm font-medium text-slate-700">
              知识库
            </label>
            <select
              value={kbId}
              onChange={(e) => setKbId(e.target.value ? Number(e.target.value) : "")}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
            >
              <option value="">请选择</option>
              {kbs.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-1">
            <label className="block text-sm font-medium text-slate-700">
              返回数量 top_k
            </label>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
            />
          </div>
          <div className="flex items-end md:col-span-1">
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? "检索中..." : "检索"}
            </button>
          </div>
        </div>
        <div className="mt-4">
          <label className="block text-sm font-medium text-slate-700">
            查询内容
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            required
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
            placeholder="输入要检索的问题..."
          />
        </div>
      </form>

      {error && (
        <div className="mt-4 rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {results.length > 0 && (
        <div className="mt-6 space-y-3">
          <h2 className="text-lg font-semibold text-slate-800">
            检索结果（{results.length}）
          </h2>
          {results.map((item, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-slate-400">
                  RRF 融合分数：{(item.score ?? 0).toFixed(4)}
                </span>
                <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-600">
                  排名 #{idx + 1}
                </span>
              </div>
              <p className="whitespace-pre-wrap text-sm text-slate-700">
                {item.content}
              </p>
              {item.metadata && Object.keys(item.metadata).length > 0 && (
                <div className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-400">
                  <span className="mr-3">
                    向量检索名次：{item.dense_rank ?? "未命中"}
                  </span>
                  <span className="mr-3">
                    BM25 名次：{item.bm25_rank ?? "未命中"}
                  </span>
                  {Object.entries(item.metadata).map(([k, v]) => (
                    <span key={k} className="mr-3">
                      {k}: {String(v)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
