# -*- coding: utf-8 -*-
"""UI 自动化序列化器"""

from rest_framework import serializers
from .models import (
    UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed,
    UiTestCase, UiCaseStepsDetailed, UiExecutionRecord, UiPublicData, UiEnvironmentConfig,
    UiBatchExecutionRecord
)


class UiModuleSerializer(serializers.ModelSerializer):
    """模块序列化器"""
    children = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiModule
        fields = ['id', 'project', 'name', 'parent', 'level', 'children', 'creator', 'creator_name', 'created_at', 'updated_at']
        read_only_fields = ['level', 'creator', 'created_at', 'updated_at']

    def get_children(self, obj):
        children = obj.children.all()
        return UiModuleSerializer(children, many=True).data if children else []


class UiElementSerializer(serializers.ModelSerializer):
    """元素序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiElement
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class UiPageSerializer(serializers.ModelSerializer):
    """页面序列化器"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    element_count = serializers.SerializerMethodField()

    class Meta:
        model = UiPage
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']

    def get_element_count(self, obj):
        return obj.elements.count()


class UiPageDetailSerializer(UiPageSerializer):
    """页面详情序列化器（含元素列表）"""
    elements = UiElementSerializer(many=True, read_only=True)

    class Meta(UiPageSerializer.Meta):
        fields = '__all__'


class UiPageStepsDetailedSerializer(serializers.ModelSerializer):
    """步骤详情序列化器"""
    element_name = serializers.CharField(source='element.name', read_only=True)

    class Meta:
        model = UiPageStepsDetailed
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class UiPageStepsDetailedExecuteSerializer(serializers.ModelSerializer):
    """步骤详情序列化器（含元素定位信息，用于执行器）"""
    element_name = serializers.CharField(source='element.name', read_only=True)
    locator_type = serializers.CharField(source='element.locator_type', read_only=True)
    locator_value = serializers.CharField(source='element.locator_value', read_only=True)
    wait_time = serializers.IntegerField(source='element.wait_time', read_only=True)

    class Meta:
        model = UiPageStepsDetailed
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class UiPageStepsListSerializer(serializers.ModelSerializer):
    """页面步骤列表序列化器（精简字段，提升性能）"""
    page_name = serializers.CharField(source='page.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiPageSteps
        fields = [
            'id', 'project', 'page', 'page_name', 'module', 'module_name',
            'name', 'status', 'step_count', 'creator', 'creator_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.step_details.count()


class UiPageStepsSerializer(serializers.ModelSerializer):
    """页面步骤序列化器"""
    page_name = serializers.CharField(source='page.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiPageSteps
        fields = '__all__'
        read_only_fields = ['status', 'result_data', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.step_details.count()


class UiPageStepsDetailSerializer(UiPageStepsSerializer):
    """页面步骤详情序列化器（含步骤详情列表）"""
    step_details = UiPageStepsDetailedSerializer(many=True, read_only=True)

    class Meta(UiPageStepsSerializer.Meta):
        fields = '__all__'


class UiPageStepsExecuteSerializer(UiPageStepsSerializer):
    """页面步骤执行序列化器（含步骤详情列表和元素定位信息）"""
    step_details = UiPageStepsDetailedExecuteSerializer(many=True, read_only=True)
    page_url = serializers.CharField(source='page.url', read_only=True)

    class Meta(UiPageStepsSerializer.Meta):
        fields = '__all__'


class UiCaseStepsDetailedSerializer(serializers.ModelSerializer):
    """用例步骤序列化器"""
    page_step_name = serializers.CharField(source='page_step.name', read_only=True)

    class Meta:
        model = UiCaseStepsDetailed
        fields = '__all__'
        read_only_fields = ['status', 'error_message', 'result_data', 'created_at', 'updated_at']


class UiCaseStepsWithDetailSerializer(serializers.ModelSerializer):
    """用例步骤序列化器（含完整page_step详情）- 用于执行时获取步骤详情"""
    page_step = UiPageStepsExecuteSerializer(read_only=True)

    class Meta:
        model = UiCaseStepsDetailed
        fields = '__all__'
        read_only_fields = ['status', 'error_message', 'result_data', 'created_at', 'updated_at']


class UiTestCaseListSerializer(serializers.ModelSerializer):
    """测试用例列表序列化器（精简字段，提升性能）"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiTestCase
        fields = [
            'id', 'project', 'module', 'module_name', 'name', 'level', 'status',
            'step_count', 'creator', 'creator_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.case_steps.count()


class UiTestCaseSerializer(serializers.ModelSerializer):
    """测试用例序列化器"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiTestCase
        fields = '__all__'
        read_only_fields = ['status', 'result_data', 'error_message', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.case_steps.count()


class UiTestCaseDetailSerializer(UiTestCaseSerializer):
    """测试用例详情序列化器（含步骤列表）"""
    case_steps = UiCaseStepsDetailedSerializer(many=True, read_only=True)

    class Meta(UiTestCaseSerializer.Meta):
        fields = '__all__'


class UiTestCaseExecuteSerializer(UiTestCaseSerializer):
    """测试用例执行序列化器（含完整步骤详情，用于执行器获取数据）"""
    case_step_details = UiCaseStepsWithDetailSerializer(source='case_steps', many=True, read_only=True)

    class Meta(UiTestCaseSerializer.Meta):
        fields = '__all__'


class UiExecutionRecordListSerializer(serializers.ModelSerializer):
    """执行记录列表序列化器（精简字段，提升性能）"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    executor_name = serializers.CharField(source='executor.username', read_only=True)

    class Meta:
        model = UiExecutionRecord
        fields = [
            'id', 'batch', 'test_case', 'test_case_name', 'executor', 'executor_name',
            'status', 'trigger_type', 'start_time', 'end_time', 'duration', 'created_at'
        ]
        read_only_fields = ['created_at']


class UiExecutionRecordBatchDetailSerializer(serializers.ModelSerializer):
    """批量执行详情中的执行记录序列化器（包含步骤结果和错误信息，不含过大字段）"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    executor_name = serializers.CharField(source='executor.username', read_only=True)

    class Meta:
        model = UiExecutionRecord
        fields = [
            'id', 'batch', 'test_case', 'test_case_name', 'executor', 'executor_name',
            'status', 'trigger_type', 'start_time', 'end_time', 'duration',
            'step_results', 'screenshots', 'error_message', 'trace_path', 'created_at'
        ]
        read_only_fields = ['created_at']


class UiExecutionRecordSerializer(serializers.ModelSerializer):
    """执行记录序列化器"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    executor_name = serializers.CharField(source='executor.username', read_only=True)

    class Meta:
        model = UiExecutionRecord
        fields = '__all__'
        read_only_fields = ['created_at']


class UiPublicDataSerializer(serializers.ModelSerializer):
    """公共数据序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiPublicData
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class UiEnvironmentConfigSerializer(serializers.ModelSerializer):
    """环境配置序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiEnvironmentConfig
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class UiBatchExecutionRecordSerializer(serializers.ModelSerializer):
    """批量执行记录序列化器"""
    executor_name = serializers.CharField(source='executor.username', read_only=True)
    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = UiBatchExecutionRecord
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_success_rate(self, obj):
        if obj.total_cases == 0:
            return 0
        return round(obj.passed_cases / obj.total_cases * 100, 1)


class UiBatchExecutionRecordDetailSerializer(UiBatchExecutionRecordSerializer):
    """批量执行记录详情序列化器（含关联执行记录详情：包含步骤结果和错误信息）"""
    execution_records = UiExecutionRecordBatchDetailSerializer(many=True, read_only=True)

    class Meta(UiBatchExecutionRecordSerializer.Meta):
        fields = '__all__'
