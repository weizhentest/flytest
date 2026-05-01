from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from testcases.models import TestBug


class Command(BaseCommand):
    help = "修复历史 BUG 的状态流转字段，统一旧状态和指派人数据。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅输出待修复数量，不落库。",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        queryset = TestBug.objects.all().prefetch_related("assigned_users")
        checked_count = 0
        changed_count = 0

        with transaction.atomic():
            for bug in queryset.iterator(chunk_size=200):
                checked_count += 1
                changed_fields = set()

                assigned_ids = list(bug.assigned_users.values_list("id", flat=True))
                if bug.assigned_to_id and bug.assigned_to_id not in assigned_ids:
                    assigned_ids.insert(0, bug.assigned_to_id)
                if assigned_ids:
                    primary_assignee_id = assigned_ids[0]
                    if bug.assigned_to_id != primary_assignee_id:
                        bug.assigned_to_id = primary_assignee_id
                        changed_fields.add("assigned_to")
                    if bug.assigned_at is None:
                        bug.assigned_at = bug.updated_at or bug.opened_at or timezone.now()
                        changed_fields.add("assigned_at")
                else:
                    if bug.assigned_to_id is not None:
                        bug.assigned_to = None
                        changed_fields.add("assigned_to")
                    if bug.assigned_at is not None:
                        bug.assigned_at = None
                        changed_fields.add("assigned_at")

                normalized_status = TestBug.normalize_status_value(
                    bug.status,
                    bug.assigned_to_id,
                    bool(assigned_ids),
                )
                if bug.status != normalized_status:
                    bug.status = normalized_status
                    changed_fields.add("status")

                if normalized_status in {
                    TestBug.STATUS_FIXED,
                    TestBug.STATUS_PENDING_RETEST,
                    TestBug.STATUS_CLOSED,
                } and not bug.resolution:
                    bug.resolution = "fixed"
                    changed_fields.add("resolution")

                if normalized_status in {
                    TestBug.STATUS_FIXED,
                    TestBug.STATUS_PENDING_RETEST,
                    TestBug.STATUS_CLOSED,
                } and bug.resolved_at is None:
                    bug.resolved_at = bug.updated_at or bug.opened_at or timezone.now()
                    changed_fields.add("resolved_at")

                if normalized_status == TestBug.STATUS_CLOSED and bug.closed_at is None:
                    bug.closed_at = bug.updated_at or bug.resolved_at or bug.opened_at or timezone.now()
                    changed_fields.add("closed_at")

                if normalized_status != TestBug.STATUS_CLOSED and bug.closed_at is not None:
                    bug.closed_at = None
                    changed_fields.add("closed_at")
                if normalized_status in {
                    TestBug.STATUS_UNASSIGNED,
                    TestBug.STATUS_ASSIGNED,
                    TestBug.STATUS_CONFIRMED,
                }:
                    if bug.resolution:
                        bug.resolution = ""
                        changed_fields.add("resolution")
                    if bug.resolved_at is not None:
                        bug.resolved_at = None
                        changed_fields.add("resolved_at")
                    if bug.resolved_by_id is not None:
                        bug.resolved_by = None
                        changed_fields.add("resolved_by")
                    if bug.closed_at is not None:
                        bug.closed_at = None
                        changed_fields.add("closed_at")
                    if bug.closed_by_id is not None:
                        bug.closed_by = None
                        changed_fields.add("closed_by")

                if not changed_fields:
                    continue

                changed_count += 1
                if dry_run:
                    continue

                changed_fields.add("updated_at")
                bug.save(update_fields=list(changed_fields))
                if assigned_ids:
                    bug.assigned_users.set(assigned_ids)
                else:
                    bug.assigned_users.clear()

            if dry_run:
                transaction.set_rollback(True)

        suffix = "（未写入，仅预览）" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"检查 BUG {checked_count} 条，修复 {changed_count} 条{suffix}"
            )
        )
