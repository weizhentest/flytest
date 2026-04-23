from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.auth import User


class ImportExportTemplate(Base):
    __tablename__ = "testcase_templates_importexporttemplate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    template_type: Mapped[str] = mapped_column(String(10), default="import")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template_file: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_headers: Mapped[list] = mapped_column(JSON, default=list)
    header_row: Mapped[int] = mapped_column(Integer, default=1)
    data_start_row: Mapped[int] = mapped_column(Integer, default=2)
    field_mappings: Mapped[dict] = mapped_column(JSON, default=dict)
    value_transformations: Mapped[dict] = mapped_column(JSON, default=dict)
    step_parsing_mode: Mapped[str] = mapped_column(String(20), default="single_cell")
    step_config: Mapped[dict] = mapped_column(JSON, default=dict)
    module_path_delimiter: Mapped[str] = mapped_column(String(10), default="/")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[User | None] = relationship(lazy="selectin")
