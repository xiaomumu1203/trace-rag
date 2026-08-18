from sqlalchemy import create_engine, text
from app.core.config import settings

def clean_database():
    engine = create_engine(settings.get_mysql_url())
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text("DROP TABLE IF EXISTS processing_tasks"))
        conn.execute(text("DROP TABLE IF EXISTS document_uploads"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(text("DROP TABLE IF EXISTS document_chunks"))
        conn.execute(text("DROP TABLE IF EXISTS chat_knowledge_bases"))
        conn.execute(text("DROP TABLE IF EXISTS documents"))
        conn.execute(text("DROP TABLE IF EXISTS knowledge_bases"))
        conn.execute(text("DROP TABLE IF EXISTS messages"))
        conn.execute(text("DROP TABLE IF EXISTS chats"))
        conn.execute(text("DROP TABLE IF EXISTS api_keys"))
        conn.execute(text("DROP TABLE IF EXISTS users"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

if __name__ == "__main__":
    clean_database()
    print("Database cleaned successfully") 