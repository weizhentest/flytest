from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.compat.requirements_runtime import (
    adjust_modules,
    analyze_document_structure,
    check_context_limit,
    confirm_modules,
    get_document_image,
    list_document_images,
    module_operations,
    restart_review,
    review_progress,
    split_modules,
    start_review,
)
from app.core.errors import AppError
from app.db.models.projects import Project
from app.db.models.requirements import (
    ModuleReviewResult,
    RequirementDocument,
    RequirementModule,
    ReviewIssue,
    ReviewReport,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
DJANGO_MEDIA_ROOT = REPO_ROOT / "FlyTest_Django" / "media"


def _get_accessible_projects(db: Session, *, user_id: int, is_superuser: bool):
    stmt = select(Project)
    if not is_superuser:
        stmt = stmt.where(Project.members.any(user_id=user_id))
    return stmt


def _uuid_candidates(value: str | None) -> list[str]:
    if not value:
        return []
    text = str(value)
    compact = text.replace("-", "")
    if compact == text:
        return [text]
    return [text, compact]


def _get_document(db: Session, *, user_id: int, is_superuser: bool, document_id: str) -> RequirementDocument:
    stmt = (
        select(RequirementDocument)
        .where(RequirementDocument.id.in_(_uuid_candidates(document_id)))
        .options(
            selectinload(RequirementDocument.project),
            selectinload(RequirementDocument.uploader),
            selectinload(RequirementDocument.modules),
            selectinload(RequirementDocument.review_reports),
        )
    )
    if not is_superuser:
        stmt = stmt.where(RequirementDocument.project.has(Project.members.any(user_id=user_id)))
    document = db.scalar(stmt)
    if not document:
        raise AppError("Requirement document not found", status_code=404)
    return document


def _get_module(db: Session, *, user_id: int, is_superuser: bool, module_id: str) -> RequirementModule:
    stmt = (
        select(RequirementModule)
        .where(RequirementModule.id.in_(_uuid_candidates(module_id)))
        .options(selectinload(RequirementModule.document))
    )
    if not is_superuser:
        stmt = stmt.where(RequirementModule.document.has(RequirementDocument.project.has(Project.members.any(user_id=user_id))))
    module = db.scalar(stmt)
    if not module:
        raise AppError("Requirement module not found", status_code=404)
    return module


def _get_report(db: Session, *, user_id: int, is_superuser: bool, report_id: str) -> ReviewReport:
    stmt = (
        select(ReviewReport)
        .where(ReviewReport.id.in_(_uuid_candidates(report_id)))
        .options(selectinload(ReviewReport.document))
    )
    if not is_superuser:
        stmt = stmt.where(ReviewReport.document.has(RequirementDocument.project.has(Project.members.any(user_id=user_id))))
    report = db.scalar(stmt)
    if not report:
        raise AppError("Review report not found", status_code=404)
    return report


def _get_issue(db: Session, *, user_id: int, is_superuser: bool, issue_id: str) -> ReviewIssue:
    stmt = (
        select(ReviewIssue)
        .where(ReviewIssue.id.in_(_uuid_candidates(issue_id)))
        .options(selectinload(ReviewIssue.report), selectinload(ReviewIssue.module))
    )
    if not is_superuser:
        stmt = stmt.where(ReviewIssue.report.has(ReviewReport.document.has(RequirementDocument.project.has(Project.members.any(user_id=user_id)))))
    issue = db.scalar(stmt)
    if not issue:
        raise AppError("Review issue not found", status_code=404)
    return issue


def _get_module_result(db: Session, *, user_id: int, is_superuser: bool, result_id: str) -> ModuleReviewResult:
    stmt = (
        select(ModuleReviewResult)
        .where(ModuleReviewResult.id.in_(_uuid_candidates(result_id)))
        .options(selectinload(ModuleReviewResult.report), selectinload(ModuleReviewResult.module))
    )
    if not is_superuser:
        stmt = stmt.where(ModuleReviewResult.report.has(ReviewReport.document.has(RequirementDocument.project.has(Project.members.any(user_id=user_id)))))
    result = db.scalar(stmt)
    if not result:
        raise AppError("Module review result not found", status_code=404)
    return result


def _serialize_document(document: RequirementDocument, *, detail: bool = False, db: Session | None = None) -> dict:
    payload = {
        "id": document.id,
        "title": document.title,
        "description": document.description,
        "document_type": document.document_type,
        "file": f"/media/{document.file}" if document.file else None,
        "content": document.content,
        "status": document.status,
        "version": document.version,
        "is_latest": document.is_latest,
        "parent_document": document.parent_document_id,
        "uploader": document.uploader_id,
        "uploader_name": document.uploader.username if document.uploader else None,
        "project": document.project_id,
        "project_name": document.project.name if document.project else None,
        "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "word_count": document.word_count,
        "page_count": document.page_count,
        "has_images": document.has_images,
        "image_count": document.image_count,
        "modules_count": len(document.modules or []),
    }
    if detail and db is not None:
        payload["modules"] = [_serialize_module(item) for item in sorted(document.modules or [], key=lambda m: (m.order, m.title))]
        reports = sorted(document.review_reports or [], key=lambda r: (r.review_date or datetime.min), reverse=True)
        payload["review_reports"] = [_serialize_report(db, report) for report in reports]
        payload["latest_review"] = _serialize_report(db, reports[0]) if reports else None
    return payload


def _serialize_module(module: RequirementModule) -> dict:
    return {
        "id": module.id,
        "document": module.document_id,
        "title": module.title,
        "content": module.content,
        "start_page": module.start_page,
        "end_page": module.end_page,
        "start_position": module.start_position,
        "end_position": module.end_position,
        "order": module.order,
        "parent_module": module.parent_module_id,
        "is_auto_generated": module.is_auto_generated,
        "confidence_score": module.confidence_score,
        "ai_suggested_title": module.ai_suggested_title,
        "created_at": module.created_at.isoformat() if module.created_at else None,
        "updated_at": module.updated_at.isoformat() if module.updated_at else None,
        "issues_count": 0,
    }


def _serialize_issue(issue: ReviewIssue) -> dict:
    return {
        "id": issue.id,
        "report": issue.report_id,
        "module": issue.module_id,
        "module_name": issue.module.title if issue.module else None,
        "issue_type": issue.issue_type,
        "issue_type_display": issue.issue_type,
        "priority": issue.priority,
        "priority_display": issue.priority,
        "title": issue.title,
        "description": issue.description,
        "suggestion": issue.suggestion,
        "location": issue.location,
        "page_number": issue.page_number,
        "section": issue.section,
        "is_resolved": issue.is_resolved,
        "resolution_note": issue.resolution_note,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
    }


def _serialize_module_result(result: ModuleReviewResult) -> dict:
    return {
        "id": result.id,
        "report": result.report_id,
        "module": result.module_id,
        "module_name": result.module.title if result.module else None,
        "module_rating": result.module_rating,
        "module_rating_display": result.module_rating,
        "issues_count": result.issues_count,
        "severity_score": result.severity_score,
        "analysis_content": result.analysis_content,
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
        "recommendations": result.recommendations,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "updated_at": result.updated_at.isoformat() if result.updated_at else None,
    }


def _serialize_report(db: Session, report: ReviewReport) -> dict:
    issues = list(db.scalars(select(ReviewIssue).where(ReviewIssue.report_id == report.id).options(selectinload(ReviewIssue.module))).all())
    module_results = list(
        db.scalars(select(ModuleReviewResult).where(ModuleReviewResult.report_id == report.id).options(selectinload(ModuleReviewResult.module))).all()
    )
    return {
        "id": report.id,
        "document": report.document_id,
        "document_title": report.document.title if report.document else None,
        "review_date": report.review_date.isoformat() if report.review_date else None,
        "reviewer": report.reviewer,
        "status": report.status,
        "status_display": report.status,
        "overall_rating": report.overall_rating,
        "overall_rating_display": report.overall_rating,
        "completion_score": report.completion_score,
        "total_issues": report.total_issues,
        "high_priority_issues": report.high_priority_issues,
        "medium_priority_issues": report.medium_priority_issues,
        "low_priority_issues": report.low_priority_issues,
        "summary": report.summary,
        "recommendations": report.recommendations,
        "issues": [_serialize_issue(item) for item in issues],
        "module_results": [_serialize_module_result(item) for item in module_results],
        "specialized_analyses": report.specialized_analyses or {},
        "scores": {
            "completeness": report.completeness_score,
            "consistency": report.consistency_score,
            "testability": report.testability_score,
            "feasibility": report.feasibility_score,
            "clarity": report.clarity_score,
            "logic": report.logic_score,
        },
        "progress": report.progress,
        "current_step": report.current_step,
        "completed_steps": list(report.completed_steps or []),
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }


def list_documents(*, db: Session, user, project: int | str | None = None, status: str | None = None, document_type: str | None = None, search: str | None = None) -> list[dict]:
    stmt = select(RequirementDocument).options(selectinload(RequirementDocument.project), selectinload(RequirementDocument.uploader), selectinload(RequirementDocument.modules))
    if not user.is_superuser:
        stmt = stmt.where(RequirementDocument.project.has(Project.members.any(user_id=user.id)))
    if project:
        stmt = stmt.where(RequirementDocument.project_id == int(project))
    if status:
        stmt = stmt.where(RequirementDocument.status == status)
    if document_type:
        stmt = stmt.where(RequirementDocument.document_type == document_type)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (RequirementDocument.title.ilike(like))
            | (RequirementDocument.description.ilike(like))
            | (RequirementDocument.content.ilike(like))
        )
    docs = list(db.scalars(stmt.order_by(RequirementDocument.uploaded_at.desc())).all())
    return [_serialize_document(item) for item in docs]


def create_document(*, db: Session, user, payload: dict[str, Any]) -> dict:
    project = db.get(Project, int(payload.get("project") or 0))
    if not project:
        raise AppError("Project not found", status_code=404)
    document_type = str(payload.get("document_type") or "")
    content = payload.get("content")
    file_obj = payload.get("file")
    if not content and not file_obj:
        raise AppError("蹇呴』鎻愪緵鏂囦欢鎴栨枃妗ｅ唴瀹?", status_code=400)

    file_rel_path = None
    if file_obj is not None:
        target_dir = DJANGO_MEDIA_ROOT / "requirement_documents" / str(project.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_name = getattr(file_obj, "name", "upload.bin")
        file_rel_path = (Path("requirement_documents") / str(project.id) / Path(file_name).name).as_posix()
        full_path = DJANGO_MEDIA_ROOT / file_rel_path
        with open(full_path, "wb") as handle:
            handle.write(file_obj.read())

    now = datetime.now()
    document = RequirementDocument(
        id=uuid4().hex,
        project_id=project.id,
        title=str(payload.get("title") or ""),
        description=payload.get("description"),
        document_type=document_type,
        file=file_rel_path,
        content=content,
        status="uploaded",
        version="1.0",
        is_latest=True,
        uploader_id=user.id,
        uploaded_at=now,
        updated_at=now,
        word_count=len(content or ""),
        page_count=max(1, (len(content or "") // 500) + 1) if content else 0,
        has_images=False,
        image_count=0,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _serialize_document(document)


def get_document(*, db: Session, user, document_id: str) -> dict:
    return _serialize_document(_get_document(db, user_id=user.id, is_superuser=user.is_superuser, document_id=document_id), detail=True, db=db)


def update_document(*, db: Session, user, document_id: str, payload: dict[str, Any]) -> dict:
    document = _get_document(db, user_id=user.id, is_superuser=user.is_superuser, document_id=document_id)
    for field in ("title", "description", "content", "status", "document_type"):
        if field in payload and payload.get(field) is not None:
            setattr(document, field, payload.get(field))
    document.updated_at = datetime.now()
    db.add(document)
    db.commit()
    db.refresh(document)
    return _serialize_document(document, detail=True, db=db)


def delete_document(*, db: Session, user, document_id: str) -> None:
    document = _get_document(db, user_id=user.id, is_superuser=user.is_superuser, document_id=document_id)
    if document.file:
        full_path = DJANGO_MEDIA_ROOT / document.file
        if full_path.exists():
            try:
                full_path.unlink()
            except Exception:
                pass
    db.delete(document)
    db.commit()


def list_modules(*, db: Session, user, document: str | None = None, search: str | None = None) -> list[dict]:
    stmt = select(RequirementModule).options(selectinload(RequirementModule.document))
    if not user.is_superuser:
        stmt = stmt.where(RequirementModule.document.has(RequirementDocument.project.has(Project.members.any(user_id=user.id))))
    if document:
        stmt = stmt.where(RequirementModule.document_id == document)
    if search:
        like = f"%{search}%"
        stmt = stmt.where((RequirementModule.title.ilike(like)) | (RequirementModule.content.ilike(like)))
    modules = list(db.scalars(stmt.order_by(RequirementModule.order.asc(), RequirementModule.created_at.asc())).all())
    return [_serialize_module(item) for item in modules]


def create_module(*, db: Session, user, payload: dict[str, Any]) -> dict:
    document = _get_document(db, user_id=user.id, is_superuser=user.is_superuser, document_id=str(payload.get("document") or ""))
    module = RequirementModule(
        id=uuid4().hex,
        document_id=document.id,
        title=str(payload.get("title") or ""),
        content=str(payload.get("content") or ""),
        order=int(payload.get("order") or 0),
        is_auto_generated=bool(payload.get("is_auto_generated", False)),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return _serialize_module(module)


def get_module(*, db: Session, user, module_id: str) -> dict:
    return _serialize_module(_get_module(db, user_id=user.id, is_superuser=user.is_superuser, module_id=module_id))


def update_module(*, db: Session, user, module_id: str, payload: dict[str, Any]) -> dict:
    module = _get_module(db, user_id=user.id, is_superuser=user.is_superuser, module_id=module_id)
    for field in ("title", "content", "order", "is_auto_generated"):
        if field in payload and payload.get(field) is not None:
            setattr(module, field, payload.get(field))
    module.updated_at = datetime.now()
    db.add(module)
    db.commit()
    db.refresh(module)
    return _serialize_module(module)


def delete_module(*, db: Session, user, module_id: str) -> None:
    module = _get_module(db, user_id=user.id, is_superuser=user.is_superuser, module_id=module_id)
    db.delete(module)
    db.commit()


def list_reports(*, db: Session, user, document: str | None = None, status: str | None = None, overall_rating: str | None = None) -> list[dict]:
    stmt = select(ReviewReport).options(selectinload(ReviewReport.document))
    if not user.is_superuser:
        stmt = stmt.where(ReviewReport.document.has(RequirementDocument.project.has(Project.members.any(user_id=user.id))))
    if document:
        stmt = stmt.where(ReviewReport.document_id == document)
    if status:
        stmt = stmt.where(ReviewReport.status == status)
    if overall_rating:
        stmt = stmt.where(ReviewReport.overall_rating == overall_rating)
    reports = list(db.scalars(stmt.order_by(ReviewReport.review_date.desc(), ReviewReport.created_at.desc())).all())
    return [_serialize_report(db, item) for item in reports]


def create_report(*, db: Session, user, payload: dict[str, Any]) -> dict:
    document = _get_document(db, user_id=user.id, is_superuser=user.is_superuser, document_id=str(payload.get("document") or ""))
    now = datetime.now()
    report = ReviewReport(
        id=uuid4().hex,
        document_id=document.id,
        review_date=now,
        reviewer=str(payload.get("reviewer") or "AI需求评审助手"),
        status=str(payload.get("status") or "pending"),
        overall_rating=payload.get("overall_rating"),
        completion_score=int(payload.get("completion_score") or 0),
        summary=str(payload.get("summary") or ""),
        recommendations=str(payload.get("recommendations") or ""),
        progress=float(payload.get("progress") or 0),
        current_step=str(payload.get("current_step") or ""),
        completed_steps=list(payload.get("completed_steps") or []),
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def get_report(*, db: Session, user, report_id: str) -> dict:
    return _serialize_report(db, _get_report(db, user_id=user.id, is_superuser=user.is_superuser, report_id=report_id))


def update_report(*, db: Session, user, report_id: str, payload: dict[str, Any]) -> dict:
    report = _get_report(db, user_id=user.id, is_superuser=user.is_superuser, report_id=report_id)
    for field in (
        "status",
        "overall_rating",
        "completion_score",
        "summary",
        "recommendations",
        "progress",
        "current_step",
        "completed_steps",
    ):
        if field in payload and payload.get(field) is not None:
            setattr(report, field, payload.get(field))
    report.updated_at = datetime.now()
    db.add(report)
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def delete_report(*, db: Session, user, report_id: str) -> None:
    report = _get_report(db, user_id=user.id, is_superuser=user.is_superuser, report_id=report_id)
    db.delete(report)
    db.commit()


def list_issues(*, db: Session, user, report: str | None = None, module: str | None = None, issue_type: str | None = None, priority: str | None = None, is_resolved: bool | None = None) -> list[dict]:
    stmt = select(ReviewIssue).options(selectinload(ReviewIssue.report), selectinload(ReviewIssue.module))
    if not user.is_superuser:
        stmt = stmt.where(ReviewIssue.report.has(ReviewReport.document.has(RequirementDocument.project.has(Project.members.any(user_id=user.id)))))
    if report:
        stmt = stmt.where(ReviewIssue.report_id == report)
    if module:
        stmt = stmt.where(ReviewIssue.module_id == module)
    if issue_type:
        stmt = stmt.where(ReviewIssue.issue_type == issue_type)
    if priority:
        stmt = stmt.where(ReviewIssue.priority == priority)
    if is_resolved is not None:
        stmt = stmt.where(ReviewIssue.is_resolved == is_resolved)
    issues = list(db.scalars(stmt.order_by(ReviewIssue.created_at.desc())).all())
    return [_serialize_issue(item) for item in issues]


def create_issue(*, db: Session, user, payload: dict[str, Any]) -> dict:
    report = db.scalar(select(ReviewReport).where(ReviewReport.id.in_(_uuid_candidates(payload.get("report")))))
    if not report:
        raise AppError("Review report not found", status_code=404)
    module = None
    if payload.get("module"):
        module = db.scalar(select(RequirementModule).where(RequirementModule.id.in_(_uuid_candidates(payload.get("module")))))
        if not module:
            raise AppError("Requirement module not found", status_code=404)
    now = datetime.now()
    issue = ReviewIssue(
        id=uuid4().hex,
        report_id=report.id,
        module_id=module.id if module else None,
        issue_type=str(payload.get("issue_type") or ""),
        priority=str(payload.get("priority") or ""),
        title=str(payload.get("title") or ""),
        description=str(payload.get("description") or ""),
        suggestion=str(payload.get("suggestion") or ""),
        location=str(payload.get("location") or ""),
        page_number=payload.get("page_number"),
        section=str(payload.get("section") or ""),
        is_resolved=bool(payload.get("is_resolved", False)),
        resolution_note=str(payload.get("resolution_note") or ""),
        created_at=now,
        updated_at=now,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return _serialize_issue(issue)


def get_issue(*, db: Session, user, issue_id: str) -> dict:
    return _serialize_issue(_get_issue(db, user_id=user.id, is_superuser=user.is_superuser, issue_id=issue_id))


def update_issue(*, db: Session, user, issue_id: str, payload: dict[str, Any]) -> dict:
    issue = _get_issue(db, user_id=user.id, is_superuser=user.is_superuser, issue_id=issue_id)
    for field in (
        "issue_type",
        "priority",
        "title",
        "description",
        "suggestion",
        "location",
        "page_number",
        "section",
        "is_resolved",
        "resolution_note",
    ):
        if field in payload and payload.get(field) is not None:
            setattr(issue, field, payload.get(field))
    issue.updated_at = datetime.now()
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return _serialize_issue(issue)


def delete_issue(*, db: Session, user, issue_id: str) -> None:
    issue = _get_issue(db, user_id=user.id, is_superuser=user.is_superuser, issue_id=issue_id)
    db.delete(issue)
    db.commit()


def list_module_results(*, db: Session, user, report: str | None = None, module: str | None = None, module_rating: str | None = None) -> list[dict]:
    stmt = select(ModuleReviewResult).options(selectinload(ModuleReviewResult.report), selectinload(ModuleReviewResult.module))
    if not user.is_superuser:
        stmt = stmt.where(ModuleReviewResult.report.has(ReviewReport.document.has(RequirementDocument.project.has(Project.members.any(user_id=user.id)))))
    if report:
        stmt = stmt.where(ModuleReviewResult.report_id == report)
    if module:
        stmt = stmt.where(ModuleReviewResult.module_id == module)
    if module_rating:
        stmt = stmt.where(ModuleReviewResult.module_rating == module_rating)
    rows = list(db.scalars(stmt.order_by(ModuleReviewResult.created_at.desc())).all())
    return [_serialize_module_result(item) for item in rows]


def create_module_result(*, db: Session, user, payload: dict[str, Any]) -> dict:
    report = db.scalar(select(ReviewReport).where(ReviewReport.id.in_(_uuid_candidates(payload.get("report")))))
    if not report:
        raise AppError("Review report not found", status_code=404)
    module = db.scalar(select(RequirementModule).where(RequirementModule.id.in_(_uuid_candidates(payload.get("module")))))
    if not module:
        raise AppError("Requirement module not found", status_code=404)
    now = datetime.now()
    result = ModuleReviewResult(
        id=uuid4().hex,
        report_id=report.id,
        module_id=module.id,
        module_rating=payload.get("module_rating"),
        issues_count=int(payload.get("issues_count") or 0),
        severity_score=int(payload.get("severity_score") or 0),
        analysis_content=str(payload.get("analysis_content") or ""),
        strengths=str(payload.get("strengths") or ""),
        weaknesses=str(payload.get("weaknesses") or ""),
        recommendations=str(payload.get("recommendations") or ""),
        created_at=now,
        updated_at=now,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return _serialize_module_result(result)


def get_module_result(*, db: Session, user, result_id: str) -> dict:
    return _serialize_module_result(_get_module_result(db, user_id=user.id, is_superuser=user.is_superuser, result_id=result_id))


def update_module_result(*, db: Session, user, result_id: str, payload: dict[str, Any]) -> dict:
    result = _get_module_result(db, user_id=user.id, is_superuser=user.is_superuser, result_id=result_id)
    for field in (
        "module_rating",
        "issues_count",
        "severity_score",
        "analysis_content",
        "strengths",
        "weaknesses",
        "recommendations",
    ):
        if field in payload and payload.get(field) is not None:
            setattr(result, field, payload.get(field))
    result.updated_at = datetime.now()
    db.add(result)
    db.commit()
    db.refresh(result)
    return _serialize_module_result(result)


def delete_module_result(*, db: Session, user, result_id: str) -> None:
    result = _get_module_result(db, user_id=user.id, is_superuser=user.is_superuser, result_id=result_id)
    db.delete(result)
    db.commit()
