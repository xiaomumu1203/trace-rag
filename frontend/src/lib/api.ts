// 统一的后端 API 客户端：处理 baseURL、JWT 鉴权、错误抛出
import type {
  APIKey,
  Chat,
  ChatMessage,
  CitationSource,
  KnowledgeBase,
  PreviewResult,
  RetrievalItem,
  TaskStatus,
  Token,
  UploadResult,
  User,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

const TOKEN_KEY = "learntrace_token";

// ---- token 管理 ----
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// ---- 通用请求封装 ----
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  isForm = false
): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!isForm && options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("learntrace:unauthorized"));
    }

    let detail = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (data.detail) detail = JSON.stringify(data.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- 认证 ----
export const authApi = {
  login: (username: string, password: string) => {
    const form = new FormData();
    form.append("username", username);
    form.append("password", password);
    return request<Token>("/auth/login", { method: "POST", body: form }, true);
  },
  register: (data: { username: string; email: string; password: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
};

// ---- 知识库 ----
export const kbApi = {
  list: () => request<KnowledgeBase[]>("/knowledge-base"),
  get: (id: number) => request<KnowledgeBase>(`/knowledge-base/${id}`),
  create: (data: { name: string; description?: string }) =>
    request<KnowledgeBase>("/knowledge-base", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: { name?: string; description?: string }) =>
    request<KnowledgeBase>(`/knowledge-base/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: number) => request<{ message: string }>(`/knowledge-base/${id}`, { method: "DELETE" }),

  uploadDocuments: (kbId: number, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<UploadResult[]>(
      `/knowledge-base/${kbId}/documents/upload`,
      { method: "POST", body: form },
      true
    );
  },

  preview: (kbId: number, body: { document_ids: number[]; chunk_size: number; chunk_overlap: number }) =>
    request<Record<number, PreviewResult>>(
      `/knowledge-base/${kbId}/documents/preview`,
      { method: "POST", body: JSON.stringify(body) }
    ),

  process: (kbId: number, uploadResults: UploadResult[]) =>
    request<{ tasks: { upload_id: number; task_id: number }[] }>(
      `/knowledge-base/${kbId}/documents/process`,
      { method: "POST", body: JSON.stringify(uploadResults) }
    ),

  taskStatus: (kbId: number, taskIds: number[]) => {
    const q = taskIds.join(",");
    return request<Record<number, TaskStatus>>(
      `/knowledge-base/${kbId}/documents/tasks?task_ids=${encodeURIComponent(q)}`
    );
  },

  testRetrieval: (body: { query: string; kb_id: number; top_k: number }) =>
    request<{ results: RetrievalItem[] }>("/knowledge-base/test-retrieval", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// ---- 聊天 ----
export const chatApi = {
  list: () => request<Chat[]>("/chat"),
  get: (id: number) => request<Chat>(`/chat/${id}`),
  messages: (id: number) => request<ChatMessage[]>(`/chat/${id}/messages`),
  create: (data: { title: string; chat_knowledge_base_ids: number[] }) =>
    request<Chat>("/chat", { method: "POST", body: JSON.stringify(data) }),
  delete: (id: number) => request<{ status: string }>(`/chat/${id}`, { method: "DELETE" }),
};

// ---- API Keys ----
export const apiKeyApi = {
  list: () => request<APIKey[]>("/api-keys"),
  create: (name: string) =>
    request<APIKey>("/api-keys", { method: "POST", body: JSON.stringify({ name }) }),
  update: (id: number, name: string) =>
    request<APIKey>(`/api-keys/${id}/update`, { method: "PUT", body: JSON.stringify({ name }) }),
  delete: (id: number) =>
    request<unknown>(`/api-keys/${id}/delete`, { method: "DELETE" }),
};

// ---- 流式聊天（SSE，Vercel AI 数据流格式）----
export async function streamChat(
  chatId: number,
  messages: ChatMessage[],
  onText: (text: string) => void,
  onSources?: (sources: CitationSource[]) => void,
): Promise<string> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/chat/${chatId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages }),
  });

  if (!res.ok) {
    let detail = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }

  if (!res.body) return "";

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const sep = trimmed.indexOf(":");
      if (sep < 0) continue;
      const type = trimmed.slice(0, sep);
      const payload = trimmed.slice(sep + 1);
      if (type === "0") {
        try {
          const text: string = JSON.parse(payload);
          full += text;
          onText(text);
        } catch {
          /* ignore malformed */
        }
      }
      if (type === "c") {
        try {
          const sources: CitationSource[] = JSON.parse(payload);
          onSources?.(sources);
        } catch {
          /* ignore malformed sources */
        }
      }
      // type "d" = 结束标记，type "e" = 错误
    }
  }
  return full;
}
