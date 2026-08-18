"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiKeyApi } from "@/lib/api";
import type { APIKey } from "@/lib/types";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [newKey, setNewKey] = useState<APIKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setKeys(await apiKeyApi.list());
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
    if (!name.trim()) return;
    setSubmitting(true);
    setError("");
    setNewKey(null);
    try {
      const key = await apiKeyApi.create(name.trim());
      setNewKey(key);
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCopy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("确定删除该 API Key？")) return;
    try {
      await apiKeyApi.delete(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">API Keys</h1>
        <p className="mt-1 text-sm text-slate-500">
          管理用于外部访问的 API 密钥
        </p>
      </div>

      <form
        onSubmit={handleCreate}
        className="mt-6 flex gap-3 rounded-xl border border-slate-200 bg-white p-4"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="输入 Key 名称"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
        />
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "创建中..." : "创建 Key"}
        </button>
      </form>

      {error && (
        <div className="mt-4 rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {newKey && (
        <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-700">
            API Key 创建成功！请立即复制保存，之后将不再显示明文：
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code className="flex-1 rounded bg-white px-3 py-2 text-sm text-green-700">
              {newKey.key}
            </code>
            <button
              onClick={() => handleCopy(newKey.key)}
              className="rounded-lg bg-green-600 px-3 py-2 text-sm text-white hover:bg-green-700"
            >
              {copied ? "已复制" : "复制"}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="mt-10 text-center text-slate-400">加载中...</div>
      ) : keys.length === 0 ? (
        <div className="mt-10 rounded-xl border border-dashed border-slate-300 p-12 text-center text-slate-400">
          暂无 API Key，创建第一个吧
        </div>
      ) : (
        <div className="mt-6 space-y-3">
          {keys.map((key) => (
            <div
              key={key.id}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4"
            >
              <div className="min-w-0">
                <div className="font-medium text-slate-800">{key.name}</div>
                <div className="mt-0.5 truncate font-mono text-xs text-slate-400">
                  {key.key}
                </div>
                {key.last_used_at && (
                  <div className="mt-0.5 text-xs text-slate-400">
                    上次使用: {key.last_used_at}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => handleDelete(key.id)}
                  className="rounded-md bg-red-50 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
