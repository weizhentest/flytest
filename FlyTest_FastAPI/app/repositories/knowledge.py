from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.knowledge import Document, KnowledgeBase, KnowledgeGlobalConfig
from app.db.models.projects import Project
from app.repositories.base import Repository


class KnowledgeRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_global_config(self) -> KnowledgeGlobalConfig | None:
        return self.db.scalar(select(KnowledgeGlobalConfig).where(KnowledgeGlobalConfig.id == 1))

    def list_knowledge_bases(
        self,
        *,
        project: int | str | None = None,
        search: str | None = None,
        is_active: bool | None = None,
        user_id: int | None = None,
        is_superuser: bool = False,
    ) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .options(selectinload(KnowledgeBase.project), selectinload(KnowledgeBase.creator), selectinload(KnowledgeBase.documents))
            .order_by(KnowledgeBase.created_at.desc(), KnowledgeBase.id.desc())
        )
        if not is_superuser and user_id is not None:
            stmt = stmt.where(KnowledgeBase.project.has(Project.members.any(user_id=user_id)))
        if project:
            stmt = stmt.where(KnowledgeBase.project_id == int(project))
        if search:
            like = f"%{search}%"
            stmt = stmt.where((KnowledgeBase.name.ilike(like)) | (KnowledgeBase.description.ilike(like)))
        if is_active is not None:
            stmt = stmt.where(KnowledgeBase.is_active == is_active)
        return list(self.db.scalars(stmt).all())

    def get_knowledge_base(self, *, kb_id: str, user_id: int | None = None, is_superuser: bool = False) -> KnowledgeBase | None:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .options(selectinload(KnowledgeBase.project), selectinload(KnowledgeBase.creator), selectinload(KnowledgeBase.documents))
        )
        if not is_superuser and user_id is not None:
            stmt = stmt.where(KnowledgeBase.project.has(Project.members.any(user_id=user_id)))
        return self.db.scalar(stmt)

    def create_knowledge_base(self, item: KnowledgeBase) -> KnowledgeBase:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_documents(
        self,
        *,
        knowledge_base: str | None = None,
        document_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        user_id: int | None = None,
        is_superuser: bool = False,
    ) -> list[Document]:
        stmt = (
            select(Document)
            .options(selectinload(Document.knowledge_base).selectinload(KnowledgeBase.project), selectinload(Document.uploader))
            .order_by(Document.uploaded_at.desc(), Document.id.desc())
        )
        if not is_superuser and user_id is not None:
            stmt = stmt.where(Document.knowledge_base.has(KnowledgeBase.project.has(Project.members.any(user_id=user_id))))
        if knowledge_base:
            stmt = stmt.where(Document.knowledge_base_id == knowledge_base)
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        if status:
            stmt = stmt.where(Document.status == status)
        if search:
            like = f"%{search}%"
            stmt = stmt.where((Document.title.ilike(like)) | (Document.content.ilike(like)))
        return list(self.db.scalars(stmt).all())

    def get_document(self, *, document_id: str, user_id: int | None = None, is_superuser: bool = False) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.knowledge_base).selectinload(KnowledgeBase.project), selectinload(Document.uploader))
        )
        if not is_superuser and user_id is not None:
            stmt = stmt.where(Document.knowledge_base.has(KnowledgeBase.project.has(Project.members.any(user_id=user_id))))
        return self.db.scalar(stmt)
