"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { kbApi } from "@/lib/api";
import type { KnowledgeBase, TaskStatus } from "@/lib/types";

const STATUS_META: Record<string, { label: string; cls: string }> = {
  pending: { label: "等待中", cls: "bg-slate-100 text-slate-600" },
  processing: { label: "处理中", cls: "bg-blue-50 text-blue-600" },
  completed: { label: "已完成", cls: "bg-green-50 text-green-600" },
  failed: { label: "失败", cls: "bg-red-50 text-red-600" },
};

function statusBadge(status: string) {
  const meta = STATUS_META[status] || {
    label: status,
    cls: "bg-slate-100 text-slate-600",
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.cls}`}>
      {meta.label}
    </span>
  );
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const kbId = Number(id);

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 上传与处理
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);

  // 任务轮询
  const [tasks, setTasks] = useState<Record<number, TaskStatus>>({});
  const [polling, setPolling] = useState(false);
  const [pollError, setPollError] = useState("");
  const taskIdsRef = useRef<number[]>([]);

  // 编辑
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const loadKb = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await kbApi.get(kbId);
      setKb(data);
      setEditName(data.name);
      setEditDesc(data.description || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    loadKb();
  }, [loadKb]);

  // 任务状态轮询
  useEffect(() => {
    if (!polling || taskIdsRef.current.length === 0) return;
    const timer = setInterval(async () => {
      try {
        const ids = [...taskIdsRef.current];
        const data = await kbApi.taskStatus(kbId, ids);
        setTasks((prev) =>
          Object.fromEntries(
            Object.entries({ ...prev, ...data }).filter(
              ([, task]) => task.status !== "completed"
            )
          )
        );

        // Preserve tasks added while this request was in flight, but stop
        // polling terminal tasks. Completed tasks move to the document list.
        const remainingIds = taskIdsRef.current.filter((taskId) => {
          const task = data[taskId];
          return !task || (task.status !== "completed" && task.status !== "failed");
        });
        taskIdsRef.current = remainingIds;
        if (remainingIds.length === 0) {
          setPolling(false);
          await loadKb();
        }
      } catch (e) {
        setPollError(e instanceof Error ? e.message : "轮询失败");
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [polling, kbId, loadKb]);

  async function handleUploadAndProcess(e: FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    const filesToUpload = [...files];
    const submittedKeys = new Set(
      filesToUpload.map((file) => `${file.name}:${file.size}:${file.lastModified}`)
    );
    const removeSubmittedFiles = () => {
      setFiles((current) =>
        current.filter(
          (file) => !submittedKeys.has(`${file.name}:${file.size}:${file.lastModified}`)
        )
      );
    };
    setUploading(true);
    setPollError("");
    setError("");
    try {
      const results = await kbApi.uploadDocuments(kbId, filesToUpload);
      const toProcess = results.filter((r) => !r.skip_processing);
      if (toProcess.length === 0) {
        alert("所选文件都已存在且处理完成，无需重复处理");
        removeSubmittedFiles();
        await loadKb();
        return;
      }
      const { tasks: taskInfos } = await kbApi.process(kbId, toProcess);
      const ids = taskInfos.map((t) => t.task_id);
      taskIdsRef.current = [...new Set([...taskIdsRef.current, ...ids])];
      // 任务刚创建时先立即展示“排队中”，无需等待下一轮轮询才出现。
      const initialTasks = Object.fromEntries(
        taskInfos.map((task) => {
          const upload = toProcess.find((item) => item.upload_id === task.upload_id);
          return [
            task.task_id,
            {
              document_id: null,
              status: "pending",
              error_message: null,
              upload_id: task.upload_id,
              file_name: upload?.file_name || null,
            },
          ];
        })
      );
      setTasks((prev) => ({ ...prev, ...initialTasks }));
      setPolling(true);
      removeSubmittedFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传/处理失败");
    } finally {
      setUploading(false);
    }
  }

  async function handleUpdate(e: FormEvent) {
    e.preventDefault();
    try {
      await kbApi.update(kbId, {
        name: editName,
        description: editDesc || undefined,
      });
      setEditing(false);
      await loadKb();
    } catch (err) {
      alert(err instanceof Error ? err.message : "更新失败");
    }
  }

  async function handleDelete() {
    if (!window.confirm("确定删除该知识库吗？该操作不可恢复。")) return;
    try {
      await kbApi.delete(kbId);
      router.push("/knowledge-bases");
    } catch (err) {
      alert(err instanceof Error ? err.message : "删除失败");
    }
  }

  if (loading) {
    return <div className="text-center text-slate-400">加载中...</div>;
  }

  if (!kb) {
    return (
      <div className="text-center text-slate-500">
        {error || "知识库不存在"}
      </div>
    );
  }

  const taskList = Object.entries(tasks);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      {/* 头部 */}
      <div className="flex items-start justify-between">
        <div>
          {editing ? (
            <form onSubmit={handleUpdate} className="space-y-3">
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-lg font-bold outline-none focus:border-brand-500"
              />
              <textarea
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm text-white hover:bg-brand-700"
                >
                  保存
                </button>
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  className="rounded-lg border border-slate-300 px-4 py-1.5 text-sm text-slate-600"
                >
                  取消
                </button>
              </div>
            </form>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-slate-800">{kb.name}</h1>
              <p className="mt-1 text-sm text-slate-500">
                {kb.description || "暂无描述"}
              </p>
            </>
          )}
        </div>
        <div className="flex gap-2">
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              编辑
            </button>
          )}
          <button
            onClick={handleDelete}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            删除知识库
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
          {error}
        </div>
      )}

      {/* 上传 */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-800">上传文档</h2>
        <form onSubmit={handleUploadAndProcess} className="space-y-4">
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.md,.txt"
            onChange={(e) => {
              const selected = Array.from(e.target.files || []);
              setFiles((current) => {
                const merged = [...current];
                const known = new Set(
                  current.map((file) => `${file.name}:${file.size}:${file.lastModified}`)
                );
                for (const file of selected) {
                  const key = `${file.name}:${file.size}:${file.lastModified}`;
                  if (!known.has(key)) {
                    known.add(key);
                    merged.push(file);
                  }
                }
                return merged;
              });
              e.currentTarget.value = "";
            }}
            className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-brand-600 hover:file:bg-brand-100"
          />
          {files.length > 0 && (
            <div className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <div className="mb-2 font-medium">已选择 {files.length} 个文件</div>
              <ul className="space-y-1">
                {files.map((file) => (
                  <li
                    key={`${file.name}:${file.size}:${file.lastModified}`}
                    className="flex items-center justify-between gap-3"
                  >
                    <span className="truncate">{file.name}</span>
                    <button
                      type="button"
                      onClick={() =>
                        setFiles((current) => current.filter((item) => item !== file))
                      }
                      className="shrink-0 text-xs text-red-500 hover:text-red-700"
                    >
                      移除
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={uploading || files.length === 0}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {uploading ? "上传并处理中..." : "上传并处理"}
            </button>
            <span className="text-xs text-slate-400">
              支持 .pdf / .docx / .md / .txt，上传后自动异步处理
            </span>
          </div>
        </form>
      </section>

      {/* 任务状态 */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">已上传文档</h2>
          <span className="text-sm text-slate-400">共 {kb.documents?.length || 0} 个</span>
        </div>

        {!kb.documents || kb.documents.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">
            暂无已处理文档，上传后会显示在这里。
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {kb.documents.map((document) => {
              const latestTask = document.processing_tasks.slice(-1)[0];
              return (
                <div key={document.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-slate-700">
                      {document.file_name}
                    </div>
                    <div className="mt-1 text-xs text-slate-400">
                      {formatFileSize(document.file_size)} · {document.content_type}
                    </div>
                  </div>
                  {latestTask ? statusBadge(latestTask.status) : statusBadge("completed")}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">处理任务</h2>
          {polling && (
            <span className="flex items-center gap-2 text-sm text-blue-600">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              正在更新处理状态...
            </span>
          )}
        </div>

        {pollError && (
          <div className="mb-3 rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
            {pollError}
          </div>
        )}

        {taskList.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">
            暂无处理任务，上传文档后这里会显示进度
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {taskList.map(([tid, task]) => (
              <div key={tid} className="flex items-center justify-between py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-700">
                    {task.file_name || `任务 #${tid}`}
                  </div>
                  <div className="text-xs text-slate-400">
                    任务 #{tid}
                    {task.document_id ? ` · 文档 ID ${task.document_id}` : ""}
                  </div>
                  {task.status === "failed" && task.error_message && (
                    <div className="mt-1 text-xs text-red-500">
                      {task.error_message}
                    </div>
                  )}
                </div>
                {statusBadge(task.status)}
              </div>
            ))}
          </div>
        )}
      </section>

    </div>
  );
}
