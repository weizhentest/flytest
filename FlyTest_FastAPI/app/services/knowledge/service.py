from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.compat.knowledge_runtime import (
    get_chunk,
    get_document_content,
    get_knowledge_base_content as compat_get_knowledge_base_content,
    get_knowledge_base_statistics,
    get_query_log,
    list_chunks,
    list_query_logs,
    query_knowledge_base,
    reprocess_document,
    system_status,
    test_embedding_connection,
    test_reranker_connection,
)
from app.core.errors import AppError
from app.db.models.knowledge import Document, KnowledgeBase, KnowledgeGlobalConfig
from app.repositories.knowledge import KnowledgeRepository
from sqlalchemy.orm import Session


REPO_ROOT = Path(__file__).resolve().parents[4]
DJANGO_MEDIA_ROOT = REPO_ROOT / "FlyTest_Django" / "media"


EMBEDDING_SERVICE_LABELS = {
    "openai": "OpenAI",
    "azure_openai": "Azure OpenAI",
    "ollama": "Ollama",
    "xinference": "Xinference",
    "custom": "自定义API",
}

RERANKER_SERVICE_LABELS = {
    "none": "不启用",
    "xinference": "Xinference",
    "custom": "自定义API",
}


def _serialize_global_config(config: KnowledgeGlobalConfig) -> dict:
    api_key = config.api_key or ""
    masked_api_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else ("*" * len(api_key) if api_key else "")
    return {
        "embedding_service": config.embedding_service,
        "embedding_service_display": EMBEDDING_SERVICE_LABELS.get(config.embedding_service, config.embedding_service),
        "api_base_url": config.api_base_url,
        "api_key": masked_api_key,
        "model_name": config.model_name,
        "reranker_service": config.reranker_service,
        "reranker_service_display": RERANKER_SERVICE_LABELS.get(config.reranker_service, config.reranker_service),
        "reranker_api_url": config.reranker_api_url,
        "reranker_api_key": config.reranker_api_key,
        "reranker_model_name": config.reranker_model_name,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        "updated_by": config.updated_by_id,
        "updated_by_name": config.updated_by.username if config.updated_by else None,
    }


def _serialize_knowledge_base(item: KnowledgeBase) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "project": item.project_id,
        "project_name": item.project.name if item.project else None,
        "creator": item.creator_id,
        "creator_name": item.creator.username if item.creator else None,
        "is_active": item.is_active,
        "chunk_size": item.chunk_size,
        "chunk_overlap": item.chunk_overlap,
        "document_count": len(item.documents or []),
        "chunk_count": 0,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_document(item: Document) -> dict:
    return {
        "id": item.id,
        "knowledge_base": item.knowledge_base_id,
        "knowledge_base_name": item.knowledge_base.name if item.knowledge_base else None,
        "title": item.title,
        "document_type": item.document_type,
        "status": item.status,
        "file_size": item.file_size,
        "page_count": item.page_count,
        "word_count": item.word_count,
        "chunk_count": 0,
        "uploader": item.uploader_id,
        "uploader_name": item.uploader.username if item.uploader else None,
        "uploaded_at": item.uploaded_at.isoformat() if item.uploaded_at else None,
        "processed_at": item.processed_at.isoformat() if item.processed_at else None,
        "url": item.url,
        "file": f"/media/{item.file}" if item.file else None,
        "file_name": Path(item.file).name if item.file else None,
        "file_url": f"/media/{item.file}" if item.file else None,
        "error_message": item.error_message,
    }


def get_global_config(*, db: Session, user) -> dict:
    repo = KnowledgeRepository(db)
    config = repo.get_global_config()
    if not config:
        config = KnowledgeGlobalConfig(
            id=1,
            embedding_service="custom",
            model_name="text-embedding-ada-002",
            reranker_service="none",
            reranker_model_name="bge-reranker-v2-m3",
            chunk_size=1000,
            chunk_overlap=200,
            updated_at=datetime.now(),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return _serialize_global_config(config)


def update_global_config(*, db: Session, user, payload: dict) -> dict:
    if not user.is_superuser:
        raise AppError("只有管理员可以修改全局配置", status_code=403)
    repo = KnowledgeRepository(db)
    config = repo.get_global_config()
    if not config:
        config = KnowledgeGlobalConfig(id=1, updated_at=datetime.now())
    for field in (
        "embedding_service",
        "api_base_url",
        "api_key",
        "model_name",
        "reranker_service",
        "reranker_api_url",
        "reranker_api_key",
        "reranker_model_name",
        "chunk_size",
        "chunk_overlap",
    ):
        if field in payload and payload.get(field) is not None:
            setattr(config, field, payload.get(field))
    config.updated_by_id = user.id
    config.updated_at = datetime.now()
    db.add(config)
    db.commit()
    db.refresh(config)
    return _serialize_global_config(config)


def embedding_services() -> dict:
    return {
        "services": [{"value": key, "label": value} for key, value in EMBEDDING_SERVICE_LABELS.items()]
    }


def list_knowledge_bases(*, db: Session, user, project=None, search: str | None = None, is_active: bool | None = None):
    items = KnowledgeRepository(db).list_knowledge_bases(
        project=project,
        search=search,
        is_active=is_active,
        user_id=user.id,
        is_superuser=user.is_superuser,
    )
    return [_serialize_knowledge_base(item) for item in items]


def create_knowledge_base(*, db: Session, user, payload: dict) -> dict:
    item = KnowledgeBase(
        id=uuid4().hex,
        name=str(payload.get("name") or ""),
        description=payload.get("description"),
        project_id=int(payload.get("project") or 0),
        creator_id=user.id,
        is_active=bool(payload.get("is_active", True)),
        chunk_size=int(payload.get("chunk_size") or 1000),
        chunk_overlap=int(payload.get("chunk_overlap") or 200),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    item = KnowledgeRepository(db).get_knowledge_base(kb_id=item.id, user_id=user.id, is_superuser=user.is_superuser)
    return _serialize_knowledge_base(item)


def get_knowledge_base(*, db: Session, user, kb_id: str) -> dict:
    item = KnowledgeRepository(db).get_knowledge_base(kb_id=kb_id, user_id=user.id, is_superuser=user.is_superuser)
    if not item:
        raise AppError("知识库不存在", status_code=404)
    return _serialize_knowledge_base(item)


def update_knowledge_base(*, db: Session, user, kb_id: str, payload: dict) -> dict:
    item = KnowledgeRepository(db).get_knowledge_base(kb_id=kb_id, user_id=user.id, is_superuser=user.is_superuser)
    if not item:
        raise AppError("知识库不存在", status_code=404)
    for field in ("name", "description", "is_active", "chunk_size", "chunk_overlap"):
        if field in payload and payload.get(field) is not None:
            setattr(item, field, payload.get(field))
    item.updated_at = datetime.now()
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_knowledge_base(item)


def delete_knowledge_base(*, db: Session, user, kb_id: str) -> None:
    item = KnowledgeRepository(db).get_knowledge_base(kb_id=kb_id, user_id=user.id, is_superuser=user.is_superuser)
    if not item:
        raise AppError("知识库不存在", status_code=404)
    db.delete(item)
    db.commit()


def list_documents(*, db: Session, user, knowledge_base=None, document_type: str | None = None, status: str | None = None, search: str | None = None):
    items = KnowledgeRepository(db).list_documents(
        knowledge_base=knowledge_base,
        document_type=document_type,
        status=status,
        search=search,
        user_id=user.id,
        is_superuser=user.is_superuser,
    )
    return [_serialize_document(item) for item in items]


def upload_document(*, db: Session, user, payload: dict) -> dict:
    kb_id = str(payload.get("knowledge_base") or "")
    knowledge_base = KnowledgeRepository(db).get_knowledge_base(kb_id=kb_id, user_id=user.id, is_superuser=user.is_superuser)
    if not knowledge_base:
        raise AppError("知识库不存在", status_code=404)
    file_obj = payload.get("file")
    file_rel_path = None
    file_size = None
    content = payload.get("content")
    if file_obj is not None:
        target_dir = DJANGO_MEDIA_ROOT / "knowledge_bases" / knowledge_base.id / "documents"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_name = Path(getattr(file_obj, "name", "upload.bin")).name
        file_rel_path = Path("knowledge_bases") / knowledge_base.id / "documents" / file_name
        full_path = DJANGO_MEDIA_ROOT / file_rel_path
        raw = file_obj.read()
        with open(full_path, "wb") as handle:
            handle.write(raw)
        file_size = len(raw)
        if not content and payload.get("document_type") in {"txt", "md"}:
            try:
                content = raw.decode("utf-8")
            except Exception:
                content = None

    item = Document(
        id=uuid4().hex,
        knowledge_base_id=knowledge_base.id,
        title=str(payload.get("title") or ""),
        document_type=str(payload.get("document_type") or ""),
        file=file_rel_path.as_posix() if file_rel_path else None,
        url=payload.get("url"),
        content=content,
        status="pending",
        file_size=file_size,
        page_count=max(1, (len(content or "") // 500) + 1) if content else None,
        word_count=len((content or "").split()) if content else None,
        uploader_id=user.id,
        uploaded_at=datetime.now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    item = KnowledgeRepository(db).get_document(document_id=item.id, user_id=user.id, is_superuser=user.is_superuser)
    return _serialize_document(item)


def get_document(*, db: Session, user, document_id: str) -> dict:
    item = KnowledgeRepository(db).get_document(document_id=document_id, user_id=user.id, is_superuser=user.is_superuser)
    if not item:
        raise AppError("文档不存在", status_code=404)
    return _serialize_document(item)


def get_document_status(*, db: Session, user, document_id: str) -> dict:
    return get_document(db=db, user=user, document_id=document_id)


def delete_document(*, db: Session, user, document_id: str) -> None:
    item = KnowledgeRepository(db).get_document(document_id=document_id, user_id=user.id, is_superuser=user.is_superuser)
    if not item:
        raise AppError("文档不存在", status_code=404)
    if item.file:
        full_path = DJANGO_MEDIA_ROOT / item.file
        if full_path.exists():
            try:
                full_path.unlink()
            except Exception:
                pass
    db.delete(item)
    db.commit()


def _normalize_uuid_values(value):
    if isinstance(value, dict):
        return {key: _normalize_uuid_values(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_normalize_uuid_values(item) for item in value]
    if isinstance(value, UUID):
        return str(value).replace("-", "")
    if isinstance(value, str) and len(value) == 36 and value.count("-") == 4:
        return value.replace("-", "")
    return value


def get_knowledge_base_content(*, user_id: int, kb_id: str, search: str = "", document_type: str = "", status: str = "completed", page: int = 1, page_size: int = 20) -> dict:
    payload = compat_get_knowledge_base_content(
        user_id=user_id,
        kb_id=kb_id,
        search=search,
        document_type=document_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return _normalize_uuid_values(payload)
