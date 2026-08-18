from sqlalchemy.engine import URL
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "TraceRAG"
    VERSION: str = "0.0.1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Chat Provider settings
    CHAT_PROVIDER: str = "deepseek"

    # OpenAI settings
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str =  "https://api.openai.com/v1"
    OPENAI_MODEL: str =  "gpt-4"

    # Deepseek settings
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"  
    DEEPSEEK_MODEL: str = "deepseek-chat"  

    # DashScope settings 
    DASH_SCOPE_API_KEY:str = ""

    # DashScope Embeddings settings 
    DASH_SCOPE_EMBEDDINGS_MODEL:str = "text-embedding-v4"

    # Huggingface settings
    HUGGINGFACE_API_KEY: str =  ""

    # Embeddings provider settings
    EMBEDDINGS_PROVIDER: str = "huggingface"
    OPENAI_EMBEDDINGS_MODEL: str = "text-embedding-ada-002"
    HUGGINGFACE_EMBEDDINGS_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # MySQL settings
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "trace_rag"
    MYSQL_PASSWORD: str = "trace_rag"
    MYSQL_DATABASE: str = "trace_rag"

    def get_mysql_url(self) -> URL:
        """
        返回一个SQLAlchemy URL对象,不可以返回字符串。URL 对象本身保存的是真实密码，
        但转成普通字符串时，SQLAlchemy 会默认把密码渲染成"***"
        """
        return URL.create(
                drivername="mysql+pymysql",
                username=self.MYSQL_USER,
                password=self.MYSQL_PASSWORD,
                host=self.MYSQL_HOST,
                port=self.MYSQL_PORT,
                database=self.MYSQL_DATABASE,
        )

    # Redis settings. Redis is a disposable cache; MySQL remains the source of truth.
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_MEMORY_TTL_SECONDS: int = 604800
    CHAT_MEMORY_MAX_MESSAGES: int = 20

    # MinIO settings
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "documents"

    # Vector Store settings
    VECTOR_STORE_TYPE: str =  "chroma"

    # Chroma DB settings
    CHROMA_DB_HOST: str = "chromadb"
    CHROMA_DB_PORT: int = 8000

    # Qdrant DB settings
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_PREFER_GRPC: bool = True

    # JWT settings
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

settings = Settings()
