FROM python:3.12-slim

WORKDIR /app

# 避免生成 .pyc 与缓冲输出；PYTHONPATH 供 import app 使用
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 系统依赖：libmagic1 供 unstructured 的 python-magic 使用（否则 .md 解析会失败）；curl 用于健康检查/调试
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖清单并安装依赖（利用 Docker 层缓存，代码改动时不用重装依赖）
COPY pyproject.toml ./

# 先安装 CPU 版 torch：本地嵌入模型用 CPU 即可，避免拉取巨大的 CUDA(nvidia-*) 依赖
# sentence-transformers 依赖 torch，看到已安装的 CPU 版满足版本要求就不会再装 CUDA 版
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
    $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

# 复制后端代码
COPY backend/ /app/

# 创建上传目录
RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
