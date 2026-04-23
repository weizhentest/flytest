from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.compat.django_bridge import ensure_django_setup, get_django_user
from app.core.errors import AppError


def _get_accessible_projects(user_id: int):
    ensure_django_setup()
    from projects.models import Project

    user = get_django_user(user_id)
    if not user:
        return Project.objects.none()
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(members__user=user).distinct()


def _accessible_documents(user_id: int):
    ensure_django_setup()
    from requirements.models import RequirementDocument

    return RequirementDocument.objects.filter(project__in=_get_accessible_projects(user_id)).distinct()


def _accessible_modules(user_id: int):
    ensure_django_setup()
    from requirements.models import RequirementModule

    return RequirementModule.objects.filter(document__project__in=_get_accessible_projects(user_id)).distinct()


def _accessible_reports(user_id: int):
    ensure_django_setup()
    from requirements.models import ReviewReport

    return ReviewReport.objects.filter(document__project__in=_get_accessible_projects(user_id)).distinct()


def _accessible_issues(user_id: int):
    ensure_django_setup()
    from requirements.models import ReviewIssue

    return ReviewIssue.objects.filter(report__document__project__in=_get_accessible_projects(user_id)).distinct()


def _accessible_module_results(user_id: int):
    ensure_django_setup()
    from requirements.models import ModuleReviewResult

    return ModuleReviewResult.objects.filter(report__document__project__in=_get_accessible_projects(user_id)).distinct()


def _request_context(user_id: int) -> dict[str, Any]:
    return {"request": SimpleNamespace(user=get_django_user(user_id))}


def _coerce_response_data(response) -> Any:
    data = getattr(response, "data", None)
    if data is None:
        return None
    if isinstance(data, dict):
        return dict(data)
    if isinstance(data, list):
        return list(data)
    return data


def _invoke_document_action(
    *,
    user_id: int,
    document_id: str,
    action_name: str,
    method: str,
    data: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
):
    ensure_django_setup()
    from requirements.views import RequirementDocumentViewSet

    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)

    request = SimpleNamespace(
        user=get_django_user(user_id),
        data=data or {},
        query_params=query_params or {},
        method=method,
    )
    view = RequirementDocumentViewSet()
    view.request = request
    view.kwargs = {"pk": str(document.id)}
    view.get_object = lambda: document
    response = getattr(view, action_name)(request, pk=str(document.id))
    status_code = getattr(response, "status_code", 200)
    payload = _coerce_response_data(response)
    if status_code >= 400:
        if isinstance(payload, dict):
            message = payload.get("error") or payload.get("detail") or payload.get("message") or "Requirement action failed"
        else:
            message = "Requirement action failed"
        raise AppError(message, status_code=status_code, errors=payload)
    return payload


def _serialize_document(document, *, detail: bool = False) -> dict:
    ensure_django_setup()
    from requirements.serializers import RequirementDocumentDetailSerializer, RequirementDocumentSerializer

    serializer_cls = RequirementDocumentDetailSerializer if detail else RequirementDocumentSerializer
    return serializer_cls(document).data


def _serialize_module(module) -> dict:
    ensure_django_setup()
    from requirements.serializers import RequirementModuleSerializer

    data = dict(RequirementModuleSerializer(module).data)
    data["document"] = str(module.document_id)
    return data


def _serialize_report(report) -> dict:
    ensure_django_setup()
    from requirements.serializers import ReviewReportSerializer

    return ReviewReportSerializer(report).data


def _serialize_issue(issue) -> dict:
    ensure_django_setup()
    from requirements.serializers import ReviewIssueSerializer

    data = dict(ReviewIssueSerializer(issue).data)
    data["report"] = str(issue.report_id)
    return data


def _serialize_module_result(result) -> dict:
    ensure_django_setup()
    from requirements.serializers import ModuleReviewResultSerializer

    data = dict(ModuleReviewResultSerializer(result).data)
    data["report"] = str(result.report_id)
    return data


def list_documents(
    *,
    user_id: int,
    project: int | str | None = None,
    status: str | None = None,
    document_type: str | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from django.db.models import Q

    queryset = _accessible_documents(user_id).select_related("project", "uploader").prefetch_related("modules", "review_reports")
    if project:
        queryset = queryset.filter(project_id=project)
    if status:
        queryset = queryset.filter(status=status)
    if document_type:
        queryset = queryset.filter(document_type=document_type)
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(content__icontains=search))
    return [_serialize_document(item) for item in queryset.order_by("-uploaded_at")]


def create_document(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import RequirementDocumentUploadSerializer
    from requirements.services import DocumentProcessor

    user = get_django_user(user_id)
    serializer = RequirementDocumentUploadSerializer(data=payload, context=_request_context(user_id))
    if not serializer.is_valid():
        raise AppError("Requirement document upload failed", status_code=400, errors=serializer.errors)

    document = serializer.save(uploader=user)
    if document.file and not document.content:
        try:
            processor = DocumentProcessor()
            content = processor.extract_content(document)
            if content:
                document.content = content
                document.word_count = len(content)
                document.page_count = max(1, (len(content) // 500) + 1)
                document.save(update_fields=["content", "word_count", "page_count", "updated_at"])
        except Exception as exc:  # noqa: BLE001
            raise AppError(f"Document content extraction failed: {exc}", status_code=500)
    return _serialize_document(document)


def get_document(*, user_id: int, document_id: str) -> dict:
    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)
    return _serialize_document(document, detail=True)


def update_document(*, user_id: int, document_id: str, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import RequirementDocumentSerializer

    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)
    serializer = RequirementDocumentSerializer(document, data=payload, partial=True, context=_request_context(user_id))
    if not serializer.is_valid():
        raise AppError("Requirement document update failed", status_code=400, errors=serializer.errors)
    document = serializer.save()
    return _serialize_document(document, detail=True)


def delete_document(*, user_id: int, document_id: str) -> None:
    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)
    if document.file:
        try:
            file_path = Path(document.file.path)
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
    document.delete()


def get_document_image(*, document_id: str, image_id: str):
    ensure_django_setup()
    from requirements.models import RequirementDocument

    document = RequirementDocument.objects.filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)
    image = document.images.filter(image_id=image_id).first()
    if not image:
        raise AppError("Document image not found", status_code=404)
    return image


def list_document_images(*, user_id: int, document_id: str) -> list[dict]:
    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)
    return [
        {
            "id": str(item.id),
            "image_id": item.image_id,
            "url": f"/api/requirements/documents/{document_id}/images/{item.image_id}/",
            "order": item.order,
            "width": item.width,
            "height": item.height,
            "file_size": item.file_size,
            "content_type": item.content_type,
        }
        for item in document.images.all().order_by("order")
    ]


def split_modules(*, user_id: int, document_id: str, payload: dict[str, Any]) -> dict:
    return _invoke_document_action(user_id=user_id, document_id=document_id, action_name="split_modules", method="POST", data=payload)


def check_context_limit(*, user_id: int, document_id: str, model_name: str | None = None) -> dict:
    return _invoke_document_action(
        user_id=user_id,
        document_id=document_id,
        action_name="check_context_limit",
        method="GET",
        query_params={"model": model_name} if model_name else {},
    )


def analyze_document_structure(*, user_id: int, document_id: str) -> dict:
    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)

    content = document.content or ""
    h1_titles: list[str] = []
    h2_titles: list[str] = []
    h3_titles: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            h3_titles.append(stripped[4:].strip())
        elif stripped.startswith("## "):
            h2_titles.append(stripped[3:].strip())
        elif stripped.startswith("# "):
            h1_titles.append(stripped[2:].strip())

    return {
        "document_id": str(document.id),
        "document_title": document.title,
        "structure_analysis": {
            "h1_titles": h1_titles,
            "h2_titles": h2_titles,
            "h3_titles": h3_titles,
            "has_hierarchy": bool(h1_titles or h2_titles or h3_titles),
        },
    }


def confirm_modules(*, user_id: int, document_id: str) -> dict:
    return _invoke_document_action(user_id=user_id, document_id=document_id, action_name="confirm_modules", method="POST")


def adjust_modules(*, user_id: int, document_id: str, payload: dict[str, Any]) -> dict:
    return _invoke_document_action(user_id=user_id, document_id=document_id, action_name="adjust_modules", method="PUT", data=payload)


def module_operations(*, user_id: int, document_id: str, payload: dict[str, Any]) -> dict:
    return _invoke_document_action(user_id=user_id, document_id=document_id, action_name="module_operations", method="POST", data=payload)


def start_review(*, user_id: int, document_id: str, payload: dict[str, Any]) -> dict:
    return _invoke_document_action(user_id=user_id, document_id=document_id, action_name="start_review", method="POST", data=payload)


def restart_review(*, user_id: int, document_id: str, payload: dict[str, Any]) -> dict:
    return _invoke_document_action(user_id=user_id, document_id=document_id, action_name="restart_review", method="POST", data=payload)


def review_progress(*, user_id: int, document_id: str) -> dict:
    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)

    latest_report = document.review_reports.order_by("-review_date").first()
    if latest_report:
        return {
            "task_id": str(latest_report.id),
            "status": latest_report.status,
            "progress": latest_report.progress,
            "current_step": latest_report.current_step,
            "completed_steps": list(latest_report.completed_steps or []),
            "document_id": str(document.id),
        }
    return {
        "task_id": str(document.id),
        "status": document.status,
        "progress": 0,
        "current_step": "",
        "completed_steps": [],
        "document_id": str(document.id),
    }


def list_modules(*, user_id: int, document: str | None = None, search: str | None = None) -> list[dict]:
    ensure_django_setup()
    from django.db.models import Q

    queryset = _accessible_modules(user_id).select_related("document", "parent_module")
    if document:
        queryset = queryset.filter(document_id=document)
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(content__icontains=search))
    return [_serialize_module(item) for item in queryset.order_by("document", "order")]


def create_module(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import RequirementModuleSerializer

    document_id = payload.get("document")
    document = _accessible_documents(user_id).filter(id=document_id).first()
    if not document:
        raise AppError("Requirement document not found", status_code=404)

    serializer = RequirementModuleSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Requirement module creation failed", status_code=400, errors=serializer.errors)
    module = serializer.save(document=document)
    return _serialize_module(module)


def get_module(*, user_id: int, module_id: str) -> dict:
    module = _accessible_modules(user_id).filter(id=module_id).first()
    if not module:
        raise AppError("Requirement module not found", status_code=404)
    return _serialize_module(module)


def update_module(*, user_id: int, module_id: str, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import RequirementModuleSerializer

    module = _accessible_modules(user_id).filter(id=module_id).first()
    if not module:
        raise AppError("Requirement module not found", status_code=404)
    serializer = RequirementModuleSerializer(module, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("Requirement module update failed", status_code=400, errors=serializer.errors)
    module = serializer.save()
    return _serialize_module(module)


def delete_module(*, user_id: int, module_id: str) -> None:
    module = _accessible_modules(user_id).filter(id=module_id).first()
    if not module:
        raise AppError("Requirement module not found", status_code=404)
    module.delete()


def list_reports(*, user_id: int, document: str | None = None, status: str | None = None, overall_rating: str | None = None) -> list[dict]:
    queryset = _accessible_reports(user_id).select_related("document")
    if document:
        queryset = queryset.filter(document_id=document)
    if status:
        queryset = queryset.filter(status=status)
    if overall_rating:
        queryset = queryset.filter(overall_rating=overall_rating)
    return [_serialize_report(item) for item in queryset.order_by("-review_date")]


def create_report(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import ReviewReportSerializer

    serializer = ReviewReportSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Review report creation failed", status_code=400, errors=serializer.errors)
    report = serializer.save()
    return _serialize_report(report)


def get_report(*, user_id: int, report_id: str) -> dict:
    report = _accessible_reports(user_id).filter(id=report_id).first()
    if not report:
        raise AppError("Review report not found", status_code=404)
    return _serialize_report(report)


def update_report(*, user_id: int, report_id: str, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import ReviewReportSerializer

    report = _accessible_reports(user_id).filter(id=report_id).first()
    if not report:
        raise AppError("Review report not found", status_code=404)
    serializer = ReviewReportSerializer(report, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("Review report update failed", status_code=400, errors=serializer.errors)
    report = serializer.save()
    return _serialize_report(report)


def delete_report(*, user_id: int, report_id: str) -> None:
    report = _accessible_reports(user_id).filter(id=report_id).first()
    if not report:
        raise AppError("Review report not found", status_code=404)
    report.delete()


def list_issues(*, user_id: int, report: str | None = None, module: str | None = None, issue_type: str | None = None, priority: str | None = None, is_resolved: bool | None = None) -> list[dict]:
    queryset = _accessible_issues(user_id).select_related("report", "module")
    if report:
        queryset = queryset.filter(report_id=report)
    if module:
        queryset = queryset.filter(module_id=module)
    if issue_type:
        queryset = queryset.filter(issue_type=issue_type)
    if priority:
        queryset = queryset.filter(priority=priority)
    if is_resolved is not None:
        queryset = queryset.filter(is_resolved=is_resolved)
    return [_serialize_issue(item) for item in queryset.order_by("-created_at")]


def create_issue(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import ReviewIssueSerializer

    report = _accessible_reports(user_id).filter(id=payload.get("report")).first()
    if not report:
        raise AppError("Review report not found", status_code=404)
    module = None
    if payload.get("module"):
        module = _accessible_modules(user_id).filter(id=payload.get("module")).first()
        if not module:
            raise AppError("Requirement module not found", status_code=404)

    serializer = ReviewIssueSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Review issue creation failed", status_code=400, errors=serializer.errors)
    issue = serializer.save(report=report, module=module)
    return _serialize_issue(issue)


def get_issue(*, user_id: int, issue_id: str) -> dict:
    issue = _accessible_issues(user_id).filter(id=issue_id).first()
    if not issue:
        raise AppError("Review issue not found", status_code=404)
    return _serialize_issue(issue)


def update_issue(*, user_id: int, issue_id: str, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import ReviewIssueSerializer

    issue = _accessible_issues(user_id).filter(id=issue_id).first()
    if not issue:
        raise AppError("Review issue not found", status_code=404)
    serializer = ReviewIssueSerializer(issue, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("Review issue update failed", status_code=400, errors=serializer.errors)
    issue = serializer.save()
    return _serialize_issue(issue)


def delete_issue(*, user_id: int, issue_id: str) -> None:
    issue = _accessible_issues(user_id).filter(id=issue_id).first()
    if not issue:
        raise AppError("Review issue not found", status_code=404)
    issue.delete()


def list_module_results(*, user_id: int, report: str | None = None, module: str | None = None, module_rating: str | None = None) -> list[dict]:
    queryset = _accessible_module_results(user_id).select_related("report", "module")
    if report:
        queryset = queryset.filter(report_id=report)
    if module:
        queryset = queryset.filter(module_id=module)
    if module_rating:
        queryset = queryset.filter(module_rating=module_rating)
    return [_serialize_module_result(item) for item in queryset.order_by("module__order")]


def create_module_result(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import ModuleReviewResultSerializer

    report = _accessible_reports(user_id).filter(id=payload.get("report")).first()
    if not report:
        raise AppError("Review report not found", status_code=404)
    module = _accessible_modules(user_id).filter(id=payload.get("module")).first()
    if not module:
        raise AppError("Requirement module not found", status_code=404)

    serializer = ModuleReviewResultSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Module review result creation failed", status_code=400, errors=serializer.errors)
    result = serializer.save(report=report, module=module)
    return _serialize_module_result(result)


def get_module_result(*, user_id: int, result_id: str) -> dict:
    result = _accessible_module_results(user_id).filter(id=result_id).first()
    if not result:
        raise AppError("Module review result not found", status_code=404)
    return _serialize_module_result(result)


def update_module_result(*, user_id: int, result_id: str, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from requirements.serializers import ModuleReviewResultSerializer

    result = _accessible_module_results(user_id).filter(id=result_id).first()
    if not result:
        raise AppError("Module review result not found", status_code=404)
    serializer = ModuleReviewResultSerializer(result, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("Module review result update failed", status_code=400, errors=serializer.errors)
    result = serializer.save()
    return _serialize_module_result(result)


def delete_module_result(*, user_id: int, result_id: str) -> None:
    result = _accessible_module_results(user_id).filter(id=result_id).first()
    if not result:
        raise AppError("Module review result not found", status_code=404)
    result.delete()
