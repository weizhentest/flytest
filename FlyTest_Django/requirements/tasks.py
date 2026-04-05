"""Requirement review background tasks."""

import logging
import threading

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import close_old_connections

logger = logging.getLogger(__name__)


def _execute_requirement_review(
    document_id,
    analysis_options=None,
    review_type="comprehensive",
    user_id=None,
):
    """Run a requirement review and persist the final status to the database."""
    from .models import RequirementDocument
    from .services import RequirementReviewService

    User = get_user_model()

    try:
        document = RequirementDocument.objects.get(id=document_id)

        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                logger.info(
                    "Starting requirement review for document %s, type=%s, user=%s",
                    document.title,
                    review_type,
                    user.username,
                )
            except User.DoesNotExist:
                logger.warning(
                    "Requirement review user %s does not exist, falling back to default prompts",
                    user_id,
                )

        review_service = RequirementReviewService(user=user)

        if review_type == "direct":
            review_report = review_service.start_direct_review(
                document,
                analysis_options or {},
            )
        else:
            review_report = review_service.start_comprehensive_review(
                document,
                analysis_options or {},
            )

        logger.info(
            "Requirement review completed for document %s, report_id=%s",
            document.title,
            review_report.id,
        )

        return {
            "status": "success",
            "document_id": str(document_id),
            "report_id": str(review_report.id),
            "completion_score": review_report.completion_score,
            "total_issues": review_report.total_issues,
        }
    except RequirementDocument.DoesNotExist:
        logger.error("Requirement document does not exist: %s", document_id)
        return {
            "status": "error",
            "message": f"Requirement document does not exist: {document_id}",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Requirement review task failed: %s", exc, exc_info=True)

        try:
            document = RequirementDocument.objects.get(id=document_id)
            document.status = "failed"
            document.save()
        except Exception:  # noqa: BLE001
            pass

        return {
            "status": "error",
            "message": str(exc),
        }


def _run_local_requirement_review(
    document_id,
    analysis_options=None,
    review_type="comprehensive",
    user_id=None,
):
    """Run the review in a local daemon thread when Celery is unavailable."""
    close_old_connections()
    try:
        _execute_requirement_review(
            document_id,
            analysis_options=analysis_options,
            review_type=review_type,
            user_id=user_id,
        )
    finally:
        close_old_connections()


def start_local_requirement_review(
    document_id,
    analysis_options=None,
    review_type="comprehensive",
    user_id=None,
):
    """Start requirement review in a local background thread."""
    worker = threading.Thread(
        target=_run_local_requirement_review,
        args=(str(document_id), analysis_options or {}, review_type, user_id),
        daemon=True,
        name=f"requirement-review-{document_id}",
    )
    worker.start()
    return worker


@shared_task(bind=True, name="requirements.execute_requirement_review")
def execute_requirement_review(
    self,
    document_id,
    analysis_options=None,
    review_type="comprehensive",
    user_id=None,
):
    return _execute_requirement_review(
        document_id,
        analysis_options=analysis_options,
        review_type=review_type,
        user_id=user_id,
    )
