// 与后端 API 对应的数据类型定义

export interface Token {
  access_token: string;
  token_type: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
}

export interface KnowledgeBase {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  documents?: Document[];
  created_at: string;
  updated_at: string;
}

export interface ProcessingTask {
  id: number;
  document_id: number | null;
  status: string; // pending | processing | completed | failed
  error_message: string | null;
  upload_id: number;
  file_name: string | null;
}

export interface Document {
  id: number;
  knowledge_base_id: number;
  file_name: string;
  file_size: number;
  content_type: string;
  processing_tasks: ProcessingTask[];
  created_at: string;
  updated_at: string;
}

export interface UploadResult {
  document_id?: number;
  upload_id?: number;
  file_name: string;
  status: string;
  message?: string;
  temp_path?: string;
  skip_processing: boolean;
}

export interface TextChunk {
  content: string;
  metadata: Record<string, unknown>;
}

export interface PreviewResult {
  chunks: TextChunk[];
  total_chunks: number;
}

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: CitationSource[];
}

export interface CitationSource {
  index: number;
  page_content: string;
  metadata: Record<string, unknown>;
  knowledge_base_name?: string | null;
  file_name?: string | null;
}

export interface Chat {
  id: number;
  user_id: number;
  title: string;
  chat_knowledge_base_ids: number[] | null;
}

export interface APIKey {
  id: number;
  key: string;
  name: string;
  user_id: number;
  last_used_at: string | null;
}

export interface RetrievalItem {
    content: string;
    metadata: Record<string, unknown>;
    score: number;
    dense_rank?: number;
    bm25_rank?: number;
}

export interface TaskStatus {
  document_id: number | null;
  status: string;
  error_message: string | null;
  upload_id: number;
  file_name: string | null;
}
