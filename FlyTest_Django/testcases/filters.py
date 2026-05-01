import django_filters
from django_filters import BaseInFilter, CharFilter, NumberFilter
from django.db.models import Q
from django.utils import timezone

from .models import TestBug, TestCase, TestCaseModule, TestSuite


class CharInFilter(BaseInFilter, CharFilter):
    """支持逗号分隔的多值文本过滤器。"""


class NumberInFilter(BaseInFilter, NumberFilter):
    """支持逗号分隔的多值数字过滤器。"""


class TestCaseFilter(django_filters.FilterSet):
    """测试用例过滤器。"""

    module_id = django_filters.NumberFilter(method="filter_by_module_and_descendants")
    level = django_filters.CharFilter(field_name="level", lookup_expr="exact")
    review_status = django_filters.CharFilter(field_name="review_status", lookup_expr="exact")
    review_status_in = CharInFilter(field_name="review_status", lookup_expr="in")
    test_type = django_filters.CharFilter(field_name="test_type", lookup_expr="exact")
    test_type_in = CharInFilter(field_name="test_type", lookup_expr="in")
    assignee_id = django_filters.NumberFilter(field_name="assignment__assignee_id", lookup_expr="exact")
    assignee_id_in = NumberInFilter(field_name="assignment__assignee_id", lookup_expr="in")
    suite_id = django_filters.NumberFilter(method="filter_by_suite_and_descendants")

    class Meta:
        model = TestCase
        fields = [
            "module_id",
            "level",
            "review_status",
            "review_status_in",
            "test_type",
            "test_type_in",
            "assignee_id",
            "assignee_id_in",
            "suite_id",
        ]

    def filter_by_module_and_descendants(self, queryset, name, value):
        """过滤指定模块及其所有子模块的用例。"""
        if value is None:
            return queryset

        try:
            module = TestCaseModule.objects.get(id=value)
        except TestCaseModule.DoesNotExist:
            return queryset.none()

        all_module_ids = module.get_all_descendant_ids()
        return queryset.filter(module_id__in=all_module_ids)

    def filter_by_suite_and_descendants(self, queryset, name, value):
        if value is None:
            return queryset

        try:
            suite = TestSuite.objects.get(id=value)
        except TestSuite.DoesNotExist:
            return queryset.none()

        all_suite_ids = suite.get_all_descendant_ids()
        return queryset.filter(test_suites__id__in=all_suite_ids).distinct()


class TestBugFilter(django_filters.FilterSet):
    suite_id = django_filters.NumberFilter(method="filter_by_suite_and_descendants")
    testcase_id = django_filters.NumberFilter(method="filter_by_testcase")
    status = django_filters.CharFilter(method="filter_by_status")
    severity = django_filters.CharFilter(field_name="severity", lookup_expr="exact")
    priority = django_filters.CharFilter(field_name="priority", lookup_expr="exact")
    bug_type = django_filters.CharFilter(field_name="bug_type", lookup_expr="exact")
    resolution = django_filters.CharFilter(field_name="resolution", lookup_expr="exact")
    assigned_to = django_filters.NumberFilter(method="filter_by_assigned_to")

    class Meta:
        model = TestBug
        fields = [
            "suite_id",
            "testcase_id",
            "status",
            "severity",
            "priority",
            "bug_type",
            "resolution",
            "assigned_to",
        ]

    def filter_by_suite_and_descendants(self, queryset, name, value):
        if value is None:
            return queryset

        try:
            suite = TestSuite.objects.get(id=value)
        except TestSuite.DoesNotExist:
            return queryset.none()

        all_suite_ids = suite.get_all_descendant_ids()
        return queryset.filter(suite_id__in=all_suite_ids)

    def filter_by_status(self, queryset, name, value):
        if not value:
            return queryset

        normalized = TestBug.normalize_status_value(value)
        if normalized == TestBug.STATUS_EXPIRED:
            return queryset.exclude(status__in=[TestBug.STATUS_CLOSED, "closed"]).filter(
                deadline__lt=timezone.localdate()
            )
        return queryset.filter(status=normalized)

    def filter_by_testcase(self, queryset, name, value):
        if value in (None, ""):
            return queryset
        return queryset.filter(
            Q(testcase_id=value) | Q(related_testcases__id=value)
        ).distinct()

    def filter_by_assigned_to(self, queryset, name, value):
        if value in (None, ""):
            return queryset
        return queryset.filter(assigned_users__id=value).distinct()
