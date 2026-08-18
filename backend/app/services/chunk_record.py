from typing import Optional, Set

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge_base import DocumentChunk


class ChunkRecord:
    def __init__(self,kb_id: int):
        self.kb_id = kb_id
        self.engine = create_engine(settings.get_mysql_url())

    def list_chunks(self, file_name: Optional[str] = None) -> Set[str]:
        with Session(self.engine) as session:
            query = session.query(DocumentChunk.hash).filter(
                DocumentChunk.knowledge_base_id == self.kb_id
            )
            if file_name:
                query = query.filter(DocumentChunk.file_name == file_name)
            return {row[0] for row in query.all()}

    def add_chunk(self, chunks: list[dict]) -> None:
        if not chunks:
            return

        with Session(self.engine) as session:
            for chunk_data in chunks:
                chunk = DocumentChunk(
                    id=chunk_data['id'],
                    knowledge_base_id=chunk_data['kb_id'],
                    document_id=chunk_data['document_id'],
                    file_name=chunk_data['file_name'],
                    content=chunk_data['content'],
                    chunk_metadata=chunk_data['metadata'],
                    hash=chunk_data['hash']
                )
                session.merge(chunk)
            session.commit()

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return

        with Session(self.engine) as session:
            session.query(DocumentChunk).filter(
                DocumentChunk.knowledge_base_id == self.kb_id,
                DocumentChunk.id.in_(chunk_ids)
            ).delete(synchronize_session=False)
            session.commit()

    def get_deleted_chunks(self, current_hashes: Set[str],file_name: Optional[str] = None) -> list[str]:
        with Session(self.engine) as session:
            query = session.query(DocumentChunk.id).filter(
                DocumentChunk.knowledge_base_id == self.kb_id,
            )
            if file_name:
                query = query.filter(DocumentChunk.file_name == file_name)
            if current_hashes:
                query = query.filter(DocumentChunk.hash.notin_(current_hashes))
            return [row[0] for row in query.all()]
