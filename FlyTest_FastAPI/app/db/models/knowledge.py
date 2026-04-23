from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.auth import User
from app.db.models.projects import Project


class KnowledgeGlobalConfig(Base):
    __tablename__ = "knowledge_knowledgeglobalconfig"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding_service: Mapped[str] = mapped_column(String(50), default="custom")
    api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), default="text-embedding-ada-002")
    reranker_service: Mapped[str] = mapped_column(String(50), default="none")
    reranker_api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reranker_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reranker_model_name: Mapped[str] = mapped_column(String(100), default="bge-reranker-v2-m3")
    chunk_size: Mapped[int] = mapped_column(Integer, default=1000)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=200)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)

    updated_by: Mapped[User | None] = relationship(lazy="selectin")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_knowledgebase"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects_project.id"))
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, default=1000)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=200)

    project: Mapped[Project] = relationship(lazy="selectin")
    creator: Mapped[User | None] = relationship(lazy="selectin")
    documents: Mapped[list["Document"]] = relationship(back_populates="knowledge_base", lazy="selectin")


class Document(Base):
    __tablename__ = "knowledge_document"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_knowledgebase.id"))
    title: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(10))
    file: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="documents", lazy="selectin")
    uploader: Mapped[User | None] = relationship(lazy="selectin")


class DocumentChunk(Base):
    __tablename__ = "knowledge_documentchunk"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document.id"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QueryLog(Base):
    __tablename__ = "knowledge_querylog"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_knowledgebase.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)
    query: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_chunks: Mapped[list] = mapped_column(JSON, default=list)
    similarity_scores: Mapped[list] = mapped_column(JSON, default=list)
    retrieval_time: Mapped[float | None] = mapped_column(nullable=True)
    generation_time: Mapped[float | None] = mapped_column(nullable=True)
    total_time: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    knowledge_base: Mapped[KnowledgeBase] = relationship(lazy="selectin")
    user: Mapped[User | None] = relationship(lazy="selectin")
