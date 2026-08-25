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

首次启动会创建基础服务；后端启动时会执行 Alembic 的 `upgrade head`，将数据库升级到已提交的最新迁移版本。

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

测试优先覆盖不依赖外部服务的核心逻辑，例如中文分词、Dense Retrieval 去重和 RRF 融合排序。

```powershell
uv run pytest
```

后续计划补充 MySQL、MinIO、向量库参与的集成测试，以及端到端的“注册 → 上传 → 处理 → 检索 → 问答”测试链路。

## 数据库迁移

日常启动时应用会自动执行最新迁移。只有在修改 SQLAlchemy 模型后，才需要生成新的 migration：

```powershell
docker compose run --rm --no-deps backend alembic -c alembic.ini revision --autogenerate -m "describe schema change"
```

生成后应人工检查 `backend/alembic/versions/` 中的 `upgrade()` 和 `downgrade()`，然后重启 backend 让它自动执行升级。

## 后续方向

- 建立 RAG 评测集，衡量检索命中率、引用正确性、延迟和成本
- 将文档处理任务迁移至可重试的队列 worker
- 提供 MCP Server，将知识库检索能力暴露为标准工具
- 为 Agent 工具调用增加权限控制、超时和可观测执行轨迹
