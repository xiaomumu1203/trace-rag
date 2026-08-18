import app.models  # 必须加载全部模型，使表注册到 Base.metadata

from app.db.migrations import run_migrations


def init_db() -> None:
    run_migrations()
