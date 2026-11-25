# TraceRAG

TraceRAG 是一个面向个人学习资料和私有文档的全栈 RAG（Retrieval-Augmented Generation）应用。用户可以创建知识库、上传文档、查看混合检索结果，并基于可追溯来源进行流式问答。

## 核心能力

- 多用户认证、知识库和会话管理
- 支持 PDF、DOCX、Markdown、TXT 文档上传、预览与分块
- Dense Retrieval 与中文 BM25 检索结合，并使用 RRF（Reciprocal Rank Fusion）融合排序
- 多知识库问答、流式响应与引用来源展示
- 面向外部系统的 API Key 检索接口
- MySQL、Redis、MinIO、Chroma / Qdrant 向量库的 Docker Compose 部署
- Alembic 管理数据库 schema 版本演进

## 架构

```text
浏览器 / 外部客户端
        │
      Nginx
   ┌────┴────┐
Next.js   FastAPI
前端        │
     ┌───────┼─────────────────────┐
   MySQL   Redis   MinIO   向量库   LLM / Embedding
```

- 浏览器通过 Nginx 访问前端页面和后端 API。
- FastAPI 负责认证、文档处理、检索、问答和流式响应。
- MySQL 保存业务数据，MinIO 保存原始文档，Redis 缓存会话历史，Chroma 或 Qdrant 保存向量。

## 项目结构

```text
TraceRAG/
├─ backend/
│  ├─ app/
│  │  ├─ api/           # FastAPI 路由：认证、知识库、聊天、API Key
│  │  ├─ core/          # 配置与 MinIO 客户端
│  │  ├─ db/            # 数据库连接与 Alembic 启动封装
│  │  ├─ models/        # SQLAlchemy 数据模型
│  │  ├─ schemas/       # 请求与响应的数据结构
│  │  ├─ services/      # 文档处理、混合检索、聊天、认证等业务逻辑
│  │  └─ main.py        # FastAPI 应用入口
│  ├─ alembic/          # 数据库迁移环境与版本文件
│  ├─ tests/            # pytest 自动化测试
│  └─ Dockerfile
├─ frontend/
│  └─ src/
│     ├─ app/           # Next.js 页面、路由与受保护页面
│     ├─ components/    # 通用 UI 组件
│     ├─ hooks/         # 认证和流式聊天等客户端逻辑
│     └─ lib/           # API 客户端与 TypeScript 类型
├─ docker-compose.yml   # 多服务部署配置
├─ nginx.conf           # 前后端反向代理配置
└─ pyproject.toml       # Python 依赖与测试配置
```

## 技术栈

- Backend: FastAPI, SQLAlchemy, Alembic, LangChain
- Retrieval: HuggingFace / OpenAI Embeddings, Chroma / Qdrant, BM25, RRF
- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Infrastructure: Docker Compose, MySQL, Redis, MinIO, Nginx

## 快速开始

### 1. 配置环境变量

从示例文件复制一份本地配置：

```powershell
Copy-Item .env.example .env
```

然后至少修改以下两类配置。

**LLM 配置**：例如使用 DeepSeek：

```env
CHAT_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat
```

**基础服务凭据**：将模板中的 `change_me` 改成自己的安全值。

```env
MYSQL_ROOT_PASSWORD=replace_with_a_strong_root_password
MYSQL_PASSWORD=replace_with_a_strong_database_password
MINIO_ACCESS_KEY=replace_with_a_minio_access_key
MINIO_SECRET_KEY=replace_with_a_minio_secret_key
SECRET_KEY=replace_with_a_long_random_jwt_secret
```

### 2. 启动服务

```powershell
Set-Location 'F:\Trace RAG'
docker compose up -d --build
```

首次启动会创建基础服务。启动后端前先单独执行一次 Alembic 迁移：

```powershell
docker compose run --rm --no-deps backend alembic -c alembic.ini upgrade head
```

这样数据库迁移与 API 进程分开：迁移失败不会让整个网站处于“前端能打开、后端不可用”的状态。

打开 `http://localhost` 使用前端，或打开 `http://localhost/docs` 查看 FastAPI OpenAPI 文档。

### 3. 停止服务

```powershell
docker compose down
```

该命令保留 MySQL、MinIO 和向量库数据。只有 `docker compose down -v` 才会删除持久化数据卷。

## 检索流程

1. 文档上传至 MinIO，并由后端解析、分块。
2. 每个分块写入 MySQL，同时写入向量库。
3. 查询时执行向量相似度检索和基于中文分词的 BM25 检索。
4. 使用 RRF 融合两个检索器的排名，避免直接混合不同量纲的原始分数。
5. 将 Top-K 上下文交给 LLM 生成带 `[citation:n]` 引用的流式回答。

## 测试

测试优先覆盖不依赖外部服务的核心逻辑，例如中文分词、Dense Retrieval 去重、三种策略选择、RRF 融合排序，以及外部 API Key 鉴权和知识库归属隔离。

```powershell
uv run pytest
```

### 检索效果评测

单元测试验证“代码没有退化”，而评测回答“检索结果好不好”。项目提供了一个离线评测脚本，用同一批人工标注的问题比较 `dense`、`bm25` 和默认的 `hybrid`（BM25 + Dense + RRF）。

1. 复制 [retrieval_cases.example.jsonl](backend/evals/retrieval_cases.example.jsonl) 为 `backend/evals/retrieval_cases.jsonl`。
2. 对每道题填写知识库 ID、真实问题，以及包含正确答案的一个或多个 `chunk_id`。`chunk_id` 可从登录后的“测试检索”结果的 `metadata.chunk_id` 获得。
3. 在 Docker 网络中执行：

```powershell
docker compose build backend
docker compose run --rm --no-deps backend python evals/run_retrieval_eval.py --cases evals/retrieval_cases.jsonl
```

输出中的 `Recall@1/3/5` 表示正确分块是否至少出现在前 1/3/5 条结果中；`MRR` 越接近 1，说明正确分块排得越靠前。建议先为一个知识库人工标注 20～30 个真实问题，再比较三种策略。

登录后的 `POST /api/v1/knowledge-bases/test-retrieval` 也支持请求体字段 `strategy: "dense" | "bm25" | "hybrid"`，便于手动查看同一问题的差异；公开的 API Key 接口始终使用默认混合检索。

## MCP Server

知识库检索能力已封装为 [MCP](https://modelcontextprotocol.io)（Model Context Protocol）Server，可被 Claude Desktop、Cursor、Cline 等任意 MCP 客户端直接调用，不必经过 HTTP 层。

```bash
python mcp_server.py          # stdio 传输，由客户端负责拉起与关闭
```

提供的原语：

| 类型 | 名称 | 说明 |
|---|---|---|
| tool | `list_knowledge_bases` | 列出指定用户的知识库 |
| tool | `search_knowledge_base` | 向量 + BM25 + RRF 混合检索，返回带来源的片段 |
| tool | `get_chunk_detail` | 按 `chunk_id` 展开片段原文，用于引用溯源 |
| resource | `trace-rag://knowledge-bases/{user_id}` | 只读知识库列表 |

依赖 `mcp>=1.2.0,<2`。冒烟测试（`kb_id`、`user_id` 按实际替换）：

```powershell
docker compose cp backend/mcp_server.py backend:/app/mcp_server.py
docker compose cp backend/mcp_smoke_test.py backend:/app/mcp_smoke_test.py
docker compose exec backend python mcp_smoke_test.py 6 2
```

两点需要注意：

- **鉴权边界**：MCP Server 直连 MySQL 与向量库，绕过了 HTTP 层的 JWT / API Key。因此工具层按 `user_id` 校验知识库归属，越权查询返回“不存在或不属于该用户”，不会泄露数据。
- **环境变量**：MCP 客户端拉起子进程时会清洗环境变量，`MYSQL_HOST`、`CHROMA_DB_HOST` 等不会被继承。以命令方式在客户端配置里启动时，需要在 `env` 字段显式传入；用 `docker compose exec` 启动则天然继承容器环境。

Claude Desktop 配置示例（`-f` 换成自己 clone 下来的 `docker-compose.yml` 绝对路径，Windows 下需写全路径并保持 Docker Desktop 在运行）：

```json
{
  "mcpServers": {
    "trace-rag": {
      "command": "docker",
      "args": [
        "compose", "-f", "/absolute/path/to/TraceRAG/docker-compose.yml",
        "exec", "-T", "backend", "python", "/app/mcp_server.py"
      ]
    }
  }
}
```

## 数据库迁移

只有在修改 SQLAlchemy 模型后，才需要生成新的 migration：

```powershell
docker compose run --rm --no-deps backend alembic -c alembic.ini revision --autogenerate -m "describe schema change"
```

生成后应人工检查 `backend/alembic/versions/` 中的 `upgrade()` 和 `downgrade()`，再执行 `alembic upgrade head`。日常只改 Python 业务代码时，不需要运行迁移命令。

## 后续方向

- 将文档处理任务迁移至可重试的队列 worker
- 为 MCP 工具调用增加超时、限流与调用审计
- 引入重排序（rerank）与端到端生成质量评测（faithfulness / answer relevancy）
