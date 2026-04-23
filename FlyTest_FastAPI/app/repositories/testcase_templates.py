from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models.testcase_templates import ImportExportTemplate
from app.repositories.base import Repository


class TestcaseTemplateRepository(Repository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def list_templates(
        self,
        *,
        template_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[ImportExportTemplate]:
        stmt = (
            select(ImportExportTemplate)
            .options(selectinload(ImportExportTemplate.creator))
            .order_by(ImportExportTemplate.updated_at.desc(), ImportExportTemplate.id.desc())
        )
        if template_type:
            stmt = stmt.where(ImportExportTemplate.template_type == template_type)
        if is_active is not None:
            stmt = stmt.where(ImportExportTemplate.is_active == is_active)
        return list(self.db.scalars(stmt).all())

    def get_template(self, *, template_id: int) -> ImportExportTemplate | None:
        stmt = (
            select(ImportExportTemplate)
            .where(ImportExportTemplate.id == template_id)
            .options(selectinload(ImportExportTemplate.creator))
        )
        return self.db.scalar(stmt)

    def get_by_name(self, *, name: str) -> ImportExportTemplate | None:
        return self.db.scalar(select(ImportExportTemplate).where(ImportExportTemplate.name == name))

    def create_template(self, item: ImportExportTemplate) -> ImportExportTemplate:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item
