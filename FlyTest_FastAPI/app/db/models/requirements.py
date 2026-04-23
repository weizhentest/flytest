from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.auth import User
from app.db.models.projects import Project


class RequirementDocument(Base):
    __tablename__ = "requirements_requirementdocument"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects_project.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(String(10))
    file: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(ForeignKey("auth_user.id"), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(lazy="selectin")
    uploader: Mapped[User | None] = relationship(lazy="selectin")
    modules: Mapped[list["RequirementModule"]] = relationship(back_populates="document", lazy="selectin")
    review_reports: Mapped[list["ReviewReport"]] = relationship(back_populates="document", lazy="selectin")


class RequirementModule(Base):
    __tablename__ = "requirements_requirementmodule"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("requirements_requirementdocument.id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    start_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    parent_module_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    ai_suggested_title: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[RequirementDocument] = relationship(back_populates="modules", lazy="selectin")


class ReviewReport(Base):
    __tablename__ = "requirements_reviewreport"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("requirements_requirementdocument.id"))
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(100), default="AI需求评审助手")
    review_type: Mapped[str] = mapped_column(String(20), default="comprehensive")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress: Mapped[float] = mapped_column(default=0)
    current_step: Mapped[str] = mapped_column(String(50), default="")
    completed_steps: Mapped[list] = mapped_column(JSON, default=list)
    overall_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    completion_score: Mapped[int] = mapped_column(Integer, default=0)
    clarity_score: Mapped[int] = mapped_column(Integer, default=0)
    consistency_score: Mapped[int] = mapped_column(Integer, default=0)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0)
    testability_score: Mapped[int] = mapped_column(Integer, default=0)
    feasibility_score: Mapped[int] = mapped_column(Integer, default=0)
    logic_score: Mapped[int] = mapped_column(Integer, default=0)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)
    high_priority_issues: Mapped[int] = mapped_column(Integer, default=0)
    medium_priority_issues: Mapped[int] = mapped_column(Integer, default=0)
    low_priority_issues: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    recommendations: Mapped[str] = mapped_column(Text, default="")
    specialized_analyses: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[RequirementDocument] = relationship(back_populates="review_reports", lazy="selectin")
    issues: Mapped[list["ReviewIssue"]] = relationship(back_populates="report", lazy="selectin")
    module_results: Mapped[list["ModuleReviewResult"]] = relationship(back_populates="report", lazy="selectin")


class ReviewIssue(Base):
    __tablename__ = "requirements_reviewissue"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("requirements_reviewreport.id"))
    module_id: Mapped[str | None] = mapped_column(ForeignKey("requirements_requirementmodule.id"), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(100), default="")
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report: Mapped[ReviewReport] = relationship(back_populates="issues", lazy="selectin")
    module: Mapped[RequirementModule | None] = relationship(lazy="selectin")


class ModuleReviewResult(Base):
    __tablename__ = "requirements_modulereviewresult"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("requirements_reviewreport.id"))
    module_id: Mapped[str] = mapped_column(ForeignKey("requirements_requirementmodule.id"))
    module_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issues_count: Mapped[int] = mapped_column(Integer, default=0)
    severity_score: Mapped[int] = mapped_column(Integer, default=0)
    analysis_content: Mapped[str] = mapped_column(Text, default="")
    strengths: Mapped[str] = mapped_column(Text, default="")
    weaknesses: Mapped[str] = mapped_column(Text, default="")
    recommendations: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report: Mapped[ReviewReport] = relationship(back_populates="module_results", lazy="selectin")
    module: Mapped[RequirementModule] = relationship(lazy="selectin")
