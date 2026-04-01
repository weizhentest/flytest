import django_filters
from django_filters import BaseInFilter, CharFilter
from .models import TestCase, TestCaseModule


class CharInFilter(BaseInFilter, CharFilter):
    """支持逗号分隔的多值过滤器"""
    pass


class TestCaseFilter(django_filters.FilterSet):
    """
    自定义测试用例过滤器，支持通过 'module_id' 和 'level' URL 参数进行过滤。
    """
    # 使用自定义过滤方法，支持包含子模块的用例
    module_id = django_filters.NumberFilter(method='filter_by_module_and_descendants')

    # 添加等级过滤器，支持通过 'level' URL 参数进行过滤
    # 例如: ?level=P2 将只返回等级为 P2 的测试用例
    # 使用 CharFilter 而不是 ChoiceFilter，这样可以更好地处理无效值
    level = django_filters.CharFilter(
        field_name='level',
        lookup_expr='exact'
    )

    # 单个审核状态过滤（保留向后兼容）
    review_status = django_filters.CharFilter(
        field_name='review_status',
        lookup_expr='exact'
    )

    # 多个审核状态过滤，支持逗号分隔，如 ?review_status_in=pending_review,approved
    review_status_in = CharInFilter(
        field_name='review_status',
        lookup_expr='in'
    )

    # 单个测试类型过滤
    test_type = django_filters.CharFilter(
        field_name='test_type',
        lookup_expr='exact'
    )

    # 多个测试类型过滤，支持逗号分隔，如 ?test_type_in=smoke,functional
    test_type_in = CharInFilter(
        field_name='test_type',
        lookup_expr='in'
    )

    class Meta:
        model = TestCase
        # fields 列表包含了我们希望 FilterSet 处理的字段。
        # DjangoFilterBackend 会查找与这些字段名匹配的 URL 参数。
        fields = ['module_id', 'level', 'review_status', 'review_status_in', 'test_type', 'test_type_in']

    def filter_by_module_and_descendants(self, queryset, name, value):
        """
        过滤指定模块及其所有子模块的用例
        """
        if value is None:
            return queryset
        
        try:
            module = TestCaseModule.objects.get(id=value)
        except TestCaseModule.DoesNotExist:
            return queryset.none()
        
        all_module_ids = module.get_all_descendant_ids()
        return queryset.filter(module_id__in=all_module_ids)