# -*- coding: utf-8 -*-
"""UI 自动化视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from data_factory.reference import build_reference_tree
from projects.models import Project

from .ai_mode import (
    build_ai_execution_report,
    get_ai_runtime_capabilities,
    request_stop_ai_execution,
    start_ai_execution,
)
from .models import (
    UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed,
    UiTestCase, UiCaseStepsDetailed, UiExecutionRecord, UiAICase, UiAIExecutionRecord,
    UiPublicData, UiEnvironmentConfig, UiBatchExecutionRecord
)
from .serializers import (
    UiModuleSerializer, UiPageSerializer, UiPageDetailSerializer,
    UiElementSerializer, UiPageStepsSerializer, UiPageStepsListSerializer, UiPageStepsDetailSerializer,
    UiPageStepsDetailedSerializer, UiTestCaseSerializer, UiTestCaseListSerializer, UiTestCaseDetailSerializer,
    UiCaseStepsDetailedSerializer, UiExecutionRecordSerializer, UiExecutionRecordListSerializer,
    UiAICaseSerializer, UiAIExecutionRecordSerializer, UiAIExecutionRecordListSerializer,
    UiPublicDataSerializer, UiEnvironmentConfigSerializer, UiTestCaseExecuteSerializer,
    UiPageStepsExecuteSerializer, UiBatchExecutionRecordSerializer, UiBatchExecutionRecordDetailSerializer
)


class UiModuleViewSet(viewsets.ModelViewSet):
    """模块管理视图"""
    queryset = UiModule.objects.select_related('project', 'parent', 'creator')
    serializer_class = UiModuleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'parent', 'level']
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['level', 'name']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取模块树形结构"""
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': 'project 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        modules = UiModule.objects.filter(project_id=project_id, parent__isnull=True)
        serializer = self.get_serializer(modules, many=True)
        return Response(serializer.data)


class UiAutomationOptionalPagination(PageNumberPagination):
    page_size = 10
    page_query_param = 'page_number'
    page_size_query_param = 'page_size'
    max_page_size = 200


class OptionalPaginationMixin:
    """
    Only enable DRF pagination when the client explicitly sends page or page_size.
    This keeps existing full-list consumers working while allowing large list pages
    to move to server-side pagination incrementally.
    """

    pagination_class = UiAutomationOptionalPagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if 'page_number' in request.query_params or 'page_size' in request.query_params:
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


def _coerce_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default


def _validate_ai_execution_request(project_id: int, execution_mode: str) -> str | None:
    capabilities = get_ai_runtime_capabilities(project_id)

    if execution_mode == 'vision':
        if not capabilities.get('llm_configured'):
            return '视觉模式需要先启用一个支持图片输入的 LLM 配置。'
        if not capabilities.get('supports_vision'):
            return '当前激活的 LLM 配置不支持视觉模式，请切换到支持图片输入的模型。'
        if not capabilities.get('vision_mode_ready'):
            return '视觉模式需要可用的 browser-use / Playwright 环境以及支持视觉能力的模型配置。'

    if execution_mode == 'text' and not capabilities.get('text_mode_ready'):
        return '文本模式当前缺少可用的执行能力，请先检查 LLM 配置和运行环境。'

    return None


class UiPageViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """页面管理视图"""
    queryset = UiPage.objects.select_related('project', 'module', 'creator')
    serializer_class = UiPageSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'module']
    search_fields = ['name', 'url']
    ordering_fields = ['name', 'created_at']
    ordering = ['-id']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UiPageDetailSerializer
        return UiPageSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UiElementViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """元素管理视图"""
    queryset = UiElement.objects.select_related('page', 'creator')
    serializer_class = UiElementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['page', 'locator_type', 'is_iframe']
    search_fields = ['name', 'locator_value']
    ordering_fields = ['name', 'created_at']
    ordering = ['-id']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class UiPageStepsViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """页面步骤管理视图"""
    queryset = UiPageSteps.objects.select_related('project', 'page', 'module', 'creator')
    serializer_class = UiPageStepsSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'page', 'module', 'status']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['-id']

    def get_queryset(self):
        """列表查询时排除大字段"""
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.defer('result_data', 'flow_data', 'run_flow', 'description')
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiPageStepsListSerializer
        if self.action == 'retrieve':
            return UiPageStepsDetailSerializer
        if self.action == 'execute_data':
            return UiPageStepsExecuteSerializer
        return UiPageStepsSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {'error': '存在关联，无法删除。请先解除关联'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='execute-data')
    def execute_data(self, request, pk=None):
        """获取页面步骤执行数据（包含元素定位信息）"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class UiPageStepsDetailedViewSet(viewsets.ModelViewSet):
    """步骤详情管理视图"""
    queryset = UiPageStepsDetailed.objects.select_related('page_step', 'element')
    serializer_class = UiPageStepsDetailedSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['page_step', 'step_type']
    ordering_fields = ['step_sort', 'created_at']
    ordering = ['page_step', 'step_sort']

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新步骤详情"""
        page_step_id = request.data.get('page_step')
        steps = request.data.get('steps', [])
        if not page_step_id:
            return Response({'error': 'page_step 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        # 删除旧步骤，创建新步骤
        UiPageStepsDetailed.objects.filter(page_step_id=page_step_id).delete()
        for idx, step_data in enumerate(steps):
            step_data['page_step'] = page_step_id
            step_data['step_sort'] = idx
            # 兼容 element_id 和 element 两种参数名
            if 'element_id' in step_data and 'element' not in step_data:
                step_data['element'] = step_data.pop('element_id')
            serializer = self.get_serializer(data=step_data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response({'message': '批量更新成功'})


class UiTestCaseViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """测试用例管理视图"""
    queryset = UiTestCase.objects.select_related('project', 'module', 'creator')
    serializer_class = UiTestCaseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'module', 'level', 'status']
    search_fields = ['name']
    ordering_fields = ['name', 'level', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """列表查询时排除大字段"""
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.defer(
                'result_data', 'front_custom', 'front_sql', 'posterior_sql',
                'parametrize', 'case_flow', 'error_message', 'description'
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiTestCaseListSerializer
        if self.action == 'retrieve':
            return UiTestCaseDetailSerializer
        if self.action == 'execute_data':
            return UiTestCaseExecuteSerializer
        return UiTestCaseSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['get'], url_path='execute-data')
    def execute_data(self, request, pk=None):
        """获取测试用例执行数据（包含完整的步骤详情）"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request, **kwargs):
        """
        批量删除UI自动化测试用例
        POST请求体格式: {"ids": [1, 2, 3, 4]}
        """
        # 获取要删除的用例ID列表
        ids_data = request.data.get('ids', [])

        if not ids_data:
            return Response(
                {'error': '请提供要删除的用例ID列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证ID格式
        try:
            testcase_ids = [int(id) for id in ids_data]
        except (ValueError, TypeError):
            return Response(
                {'error': 'ids参数格式错误，应为数字列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not testcase_ids:
            return Response(
                {'error': '用例ID列表不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取当前查询集，确保数据隔离
        queryset = self.get_queryset()

        # 过滤出要删除的用例
        testcases_to_delete = queryset.filter(id__in=testcase_ids)

        # 检查是否所有请求的ID都存在
        found_ids = list(testcases_to_delete.values_list('id', flat=True))
        not_found_ids = [id for id in testcase_ids if id not in found_ids]

        if not_found_ids:
            return Response(
                {
                    'error': f'以下用例ID不存在: {not_found_ids}',
                    'not_found_ids': not_found_ids
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 记录删除前的信息用于返回
        deleted_testcases_info = []
        for testcase in testcases_to_delete:
            deleted_testcases_info.append({
                'id': testcase.id,
                'name': testcase.name,
                'module': testcase.module.name if testcase.module else None
            })

        # 执行批量删除
        try:
            with transaction.atomic():
                # 删除用例（关联的步骤会因为外键级联删除而自动删除）
                deleted_count, deleted_details = testcases_to_delete.delete()

                return Response({
                    'message': f'成功删除 {len(deleted_testcases_info)} 个UI自动化测试用例',
                    'deleted_count': len(deleted_testcases_info),
                    'deleted_testcases': deleted_testcases_info,
                    'deletion_details': deleted_details
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'删除过程中发生错误: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UiCaseStepsDetailedViewSet(viewsets.ModelViewSet):
    """用例步骤管理视图"""
    queryset = UiCaseStepsDetailed.objects.select_related('test_case', 'page_step')
    serializer_class = UiCaseStepsDetailedSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['test_case', 'status']
    ordering_fields = ['case_sort', 'created_at']
    ordering = ['test_case', 'case_sort']

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新用例步骤"""
        test_case_id = request.data.get('test_case')
        steps = request.data.get('steps', [])
        if not test_case_id:
            return Response({'error': 'test_case 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        # 删除旧步骤，创建新步骤
        UiCaseStepsDetailed.objects.filter(test_case_id=test_case_id).delete()
        for idx, step_data in enumerate(steps):
            step_data['test_case'] = test_case_id
            step_data['case_sort'] = idx
            serializer = self.get_serializer(data=step_data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response({'message': '批量更新成功'})


class UiExecutionRecordViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """执行记录管理视图"""
    queryset = UiExecutionRecord.objects.select_related('test_case', 'executor')
    serializer_class = UiExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {'test_case': ['exact'], 'status': ['exact'], 'trigger_type': ['exact'], 'test_case__project': ['exact']}
    ordering_fields = ['created_at', 'duration']
    ordering = ['-created_at']

    def get_queryset(self):
        """列表查询时排除大字段，支持 project 参数过滤"""
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(test_case__project_id=project_id)
        if self.action == 'list':
            return queryset.defer(
                'step_results', 'screenshots', 'trace_data', 'log',
                'error_message', 'environment'
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiExecutionRecordListSerializer
        return UiExecutionRecordSerializer

    def perform_create(self, serializer):
        serializer.save(executor=self.request.user)

    def perform_destroy(self, instance):
        """删除执行记录及其关联文件"""
        import os
        from django.conf import settings

        def safe_delete(path):
            if not path:
                return
            full_path = path if os.path.isabs(path) else os.path.join(settings.MEDIA_ROOT, path.lstrip('/'))
            if os.path.exists(full_path):
                os.remove(full_path)

        # 删除截图
        for screenshot in instance.screenshots or []:
            if isinstance(screenshot, str):
                safe_delete(screenshot.replace(settings.MEDIA_URL, ''))

        # 删除视频
        safe_delete(instance.video_path)

        # 删除 Trace 文件
        safe_delete(instance.trace_path)

        instance.delete()
    
    @action(detail=True, methods=['get'], url_path='trace')
    def get_trace_data(self, request, pk=None):
        """获取执行记录的 Trace 数据

        如果 trace_data 已解析则直接返回，否则尝试解析 trace_path
        可通过 ?refresh=1 强制重新解析
        """
        instance = self.get_object()
        refresh = request.query_params.get('refresh', '').lower() in ('1', 'true')

        # 如果已有解析数据且不需要刷新，直接返回
        if instance.trace_data and not refresh:
            return Response({
                'status': 'success',
                'data': instance.trace_data
            })
        
        # 尝试解析 trace 文件
        if not instance.trace_path:
            return Response({
                'status': 'error',
                'message': '此执行记录没有 Trace 数据'
            }, status=status.HTTP_404_NOT_FOUND)
        
        from .trace_parser import parse_trace_file
        import os
        from django.conf import settings
        
        # 构建完整路径
        trace_path = instance.trace_path
        if not os.path.isabs(trace_path):
            trace_path = os.path.join(settings.MEDIA_ROOT, trace_path)
        
        trace_data = parse_trace_file(trace_path)
        if not trace_data:
            return Response({
                'status': 'error',
                'message': 'Trace 文件解析失败'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 保存解析结果
        instance.trace_data = trace_data
        instance.save(update_fields=['trace_data'])
        
        return Response({
            'status': 'success',
            'data': trace_data
        })


class UiPublicDataViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """公共数据管理视图"""
    queryset = UiPublicData.objects.select_related('project', 'creator')
    serializer_class = UiPublicDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'type', 'is_enabled']
    search_fields = ['key']
    ordering_fields = ['key', 'created_at']
    ordering = ['project', 'key']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=False, methods=['get'], url_path='by-project/(?P<project_id>[^/.]+)')
    def by_project(self, request, project_id=None):
        """获取指定项目的所有启用公共数据（供执行器使用）
        
        返回格式（经 UnifiedResponseRenderer 包装后）:
        {"status": "success", "code": 200, "data": [{"key": "username", "value": "admin", "type": 0}, ...]}
        """
        public_data = list(
            UiPublicData.objects.filter(
                project_id=project_id,
                is_enabled=True
            ).values('key', 'value', 'type')
        )
        public_data.append({
            'key': 'df',
            'value': build_reference_tree(int(project_id)),
            'type': 3,
        })
        # 直接返回列表，由 UnifiedResponseRenderer 统一包装为标准格式
        return Response(public_data)


class UiEnvironmentConfigViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """环境配置管理视图"""
    queryset = UiEnvironmentConfig.objects.select_related('project', 'creator')
    serializer_class = UiEnvironmentConfigSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'browser', 'headless', 'is_default']
    search_fields = ['name', 'base_url']
    ordering_fields = ['name', 'created_at']
    ordering = ['project', 'name']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class ActuatorViewSet(viewsets.ViewSet):
    """执行器管理视图"""
    permission_classes = []  # 公开访问，不需要特殊权限

    @action(detail=False, methods=['get'])
    def list_actuators(self, request):
        """获取所有在线执行器列表"""
        from .consumers import SocketUserManager

        actuators = []
        for actuator_id, consumer in SocketUserManager._actuator_users.items():
            actuator_info = getattr(consumer, 'actuator_info', {})
            actuators.append({
                'id': actuator_id,
                'name': actuator_info.get('name', actuator_id),
                'ip': actuator_info.get('ip', 'unknown'),
                'type': actuator_info.get('type', 'web_ui'),
                'is_open': actuator_info.get('is_open', True),
                'debug': actuator_info.get('debug', False),
                'browser_type': actuator_info.get('browser_type', 'chromium'),
                'headless': actuator_info.get('headless', False),
                'connected_at': actuator_info.get('connected_at'),
            })

        return Response({
            'status': 'success',
            'data': {
                'count': len(actuators),
                'items': actuators
            }
        })

    @action(detail=False, methods=['get'])
    def status(self, request):
        """获取执行器状态统计"""
        from .consumers import SocketUserManager

        return Response({
            'status': 'success',
            'data': {
                'total_actuators': SocketUserManager.get_actuator_count(),
                'has_available': SocketUserManager.has_actuator(),
                'web_users': len(SocketUserManager._web_users),
            }
        })


class UiBatchExecutionRecordViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """批量执行记录管理视图"""
    queryset = UiBatchExecutionRecord.objects.select_related('executor')
    serializer_class = UiBatchExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'trigger_type']
    ordering_fields = ['created_at', 'duration', 'total_cases']
    ordering = ['-created_at']

    def get_queryset(self):
        """列表查询时不预加载执行记录，支持 project 参数过滤"""
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(execution_records__test_case__project_id=project_id).distinct()
        # 详情时预加载执行记录
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('execution_records', 'execution_records__test_case')
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UiBatchExecutionRecordDetailSerializer
        return UiBatchExecutionRecordSerializer

    def perform_destroy(self, instance):
        """删除批量执行记录及其关联的执行记录"""
        instance.execution_records.all().delete()
        instance.delete()


class UiAICaseViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """AI 智能模式用例管理"""

    queryset = UiAICase.objects.select_related('project', 'creator')
    serializer_class = UiAICaseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'default_execution_mode']
    search_fields = ['name', 'description', 'task_description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        ids_data = request.data.get('ids', [])
        if not isinstance(ids_data, list) or not ids_data:
            return Response({'error': '请提供要删除的 AI 用例 ID 列表'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            case_ids = [int(item) for item in ids_data]
        except (TypeError, ValueError):
            return Response({'error': 'ids 参数格式错误，应为数字列表'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(id__in=case_ids)
        found_ids = list(queryset.values_list('id', flat=True))
        missing_ids = [case_id for case_id in case_ids if case_id not in found_ids]
        if missing_ids:
            return Response(
                {'error': f'以下 AI 用例不存在: {missing_ids}', 'missing_ids': missing_ids},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted_cases = list(queryset.values('id', 'name', 'default_execution_mode'))
        with transaction.atomic():
            deleted_count, _ = queryset.delete()

        return Response(
            {
                'message': f'成功删除 {deleted_count} 条 AI 用例',
                'deleted_count': deleted_count,
                'deleted_cases': deleted_cases,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        ai_case = self.get_object()
        execution_mode = request.data.get('execution_mode') or ai_case.default_execution_mode or 'text'

        if execution_mode not in dict(UiAICase.EXECUTION_MODE_CHOICES):
            return Response({'error': '不支持的执行模式'}, status=status.HTTP_400_BAD_REQUEST)

        validation_error = _validate_ai_execution_request(ai_case.project_id, execution_mode)
        if validation_error:
            return Response(
                {
                    'error': validation_error,
                    'runtime_capabilities': get_ai_runtime_capabilities(ai_case.project_id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        execution_record = UiAIExecutionRecord.objects.create(
            project=ai_case.project,
            ai_case=ai_case,
            case_name=ai_case.name,
            task_description=ai_case.task_description,
            execution_mode=execution_mode,
            enable_gif=_coerce_bool(request.data.get('enable_gif'), ai_case.enable_gif),
            status='running',
            executed_by=request.user,
            logs='',
        )
        start_ai_execution(execution_record.id)

        serializer = UiAIExecutionRecordSerializer(execution_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UiAIExecutionRecordViewSet(OptionalPaginationMixin, viewsets.ModelViewSet):
    """AI 智能模式执行记录管理"""

    queryset = UiAIExecutionRecord.objects.select_related('project', 'ai_case', 'executed_by')
    serializer_class = UiAIExecutionRecordSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'ai_case', 'execution_mode', 'status', 'execution_backend']
    search_fields = ['case_name', 'task_description']
    ordering_fields = ['start_time', 'end_time', 'duration']
    ordering = ['-start_time']
    active_delete_statuses = {'pending', 'running'}

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.defer('logs', 'planned_tasks', 'steps_completed', 'screenshots_sequence', 'error_message')
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return UiAIExecutionRecordListSerializer
        return UiAIExecutionRecordSerializer

    def destroy(self, request, *args, **kwargs):
        record = self.get_object()
        if record.status in self.active_delete_statuses:
            return Response({'error': '执行中的任务请先停止后再删除'}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_destroy(record)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='capabilities')
    def capabilities(self, request):
        project_id = request.query_params.get('project')

        if project_id not in (None, ''):
            project = Project.objects.filter(id=project_id).only('id').first()
            if project is None:
                return Response({'error': '项目不存在'}, status=status.HTTP_404_NOT_FOUND)
            capability_data = get_ai_runtime_capabilities(project.id)
        else:
            capability_data = get_ai_runtime_capabilities()

        return Response(capability_data)

    @action(detail=False, methods=['post'], url_path='run-adhoc')
    def run_adhoc(self, request):
        project_id = request.data.get('project')
        task_description = (request.data.get('task_description') or '').strip()
        execution_mode = request.data.get('execution_mode') or 'text'
        case_name = (request.data.get('case_name') or '').strip()

        if not project_id:
            return Response({'error': 'project 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        if not task_description:
            return Response({'error': 'task_description 参数必填'}, status=status.HTTP_400_BAD_REQUEST)
        if execution_mode not in dict(UiAICase.EXECUTION_MODE_CHOICES):
            return Response({'error': '不支持的执行模式'}, status=status.HTTP_400_BAD_REQUEST)

        project = Project.objects.filter(id=project_id).first()
        if project is None:
            return Response({'error': '项目不存在'}, status=status.HTTP_404_NOT_FOUND)

        validation_error = _validate_ai_execution_request(project.id, execution_mode)
        if validation_error:
            return Response(
                {
                    'error': validation_error,
                    'runtime_capabilities': get_ai_runtime_capabilities(project.id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        execution_record = UiAIExecutionRecord.objects.create(
            project=project,
            case_name=case_name or f"临时任务 {timezone.now().strftime('%m-%d %H:%M')}",
            task_description=task_description,
            execution_mode=execution_mode,
            enable_gif=_coerce_bool(request.data.get('enable_gif'), True),
            status='running',
            executed_by=request.user,
            logs='',
        )
        start_ai_execution(execution_record.id)

        serializer = UiAIExecutionRecordSerializer(execution_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        record = self.get_object()

        if record.status not in ['pending', 'running']:
            return Response({'error': '当前任务未在执行中'}, status=status.HTTP_400_BAD_REQUEST)

        request_stop_ai_execution(record.id)
        record.refresh_from_db()

        return Response({
            'message': '已发送停止信号',
            'data': UiAIExecutionRecordSerializer(record).data,
        })

    @action(detail=False, methods=['post'], url_path='batch-stop')
    def batch_stop(self, request):
        ids_data = request.data.get('ids', [])
        if not isinstance(ids_data, list) or not ids_data:
            return Response({'error': '请提供要停止的执行记录 ID 列表'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            record_ids = [int(item) for item in ids_data]
        except (TypeError, ValueError):
            return Response({'error': 'ids 参数格式错误，应为数字列表'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(id__in=record_ids)
        found_ids = list(queryset.values_list('id', flat=True))
        missing_ids = [record_id for record_id in record_ids if record_id not in found_ids]
        if missing_ids:
            return Response(
                {'error': f'以下执行记录不存在: {missing_ids}', 'missing_ids': missing_ids},
                status=status.HTTP_400_BAD_REQUEST
            )

        runnable_records = list(queryset.filter(status__in=self.active_delete_statuses))
        skipped_records = list(
            queryset.exclude(status__in=self.active_delete_statuses).values('id', 'case_name', 'status')
        )

        stopped_ids: list[int] = []
        for record in runnable_records:
            if request_stop_ai_execution(record.id):
                stopped_ids.append(record.id)

        stopped_records = list(
            self.get_queryset()
            .filter(id__in=stopped_ids)
            .values('id', 'case_name', 'status', 'end_time', 'duration')
        )

        return Response(
            {
                'message': f'成功停止 {len(stopped_records)} 条 AI 执行记录',
                'stopped_count': len(stopped_records),
                'stopped_records': stopped_records,
                'skipped_records': skipped_records,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        ids_data = request.data.get('ids', [])
        if not isinstance(ids_data, list) or not ids_data:
            return Response({'error': '请提供要删除的执行记录 ID 列表'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            record_ids = [int(item) for item in ids_data]
        except (TypeError, ValueError):
            return Response({'error': 'ids 参数格式错误，应为数字列表'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(id__in=record_ids)
        found_ids = list(queryset.values_list('id', flat=True))
        missing_ids = [record_id for record_id in record_ids if record_id not in found_ids]
        if missing_ids:
            return Response(
                {'error': f'以下执行记录不存在: {missing_ids}', 'missing_ids': missing_ids},
                status=status.HTTP_400_BAD_REQUEST
            )

        active_records = list(
            queryset.filter(status__in=self.active_delete_statuses).values('id', 'case_name', 'status')
        )
        if active_records:
            return Response(
                {
                    'error': '存在执行中的任务，请先停止后再删除',
                    'active_records': active_records,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted_records = list(queryset.values('id', 'case_name', 'status'))
        with transaction.atomic():
            deleted_count, _ = queryset.delete()

        return Response(
            {
                'message': f'成功删除 {deleted_count} 条 AI 执行记录',
                'deleted_count': deleted_count,
                'deleted_records': deleted_records,
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        record = self.get_object()
        report_type = (request.query_params.get('report_type') or 'summary').strip().lower()
        if report_type not in {'summary', 'detailed', 'performance'}:
            return Response(
                {'error': 'report_type 仅支持 summary、detailed、performance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(build_ai_execution_report(record, report_type=report_type))

    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None):
        record = self.get_object()
        report_type = (request.query_params.get('report_type') or 'summary').strip().lower()
        if report_type not in {'summary', 'detailed', 'performance'}:
            return Response(
                {'error': 'report_type 仅支持 summary、detailed、performance'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from .pdf_generator import AIReportPDFGenerator
        except ImportError as exc:
            return Response(
                {'error': f'PDF 导出依赖不可用: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            report_data = build_ai_execution_report(record, report_type=report_type)
            pdf_buffer = AIReportPDFGenerator(report_data, report_type=report_type).generate()
        except ImportError as exc:
            return Response(
                {'error': f'PDF 导出依赖不可用: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as exc:
            return Response(
                {'error': f'生成 PDF 失败: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        safe_case_name = ''.join(
            char if char.isalnum() or char in (' ', '_', '-') else '_'
            for char in record.case_name
        ).strip() or 'ai_report'
        filename = f'FlyTest_AI_Report_{safe_case_name}_{report_type}_{timestamp}.pdf'

        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_buffer.getvalue())
        return response


# ---------- 截图上传 ----------
import os
import uuid
from datetime import datetime
from django.conf import settings
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated


from rest_framework.permissions import AllowAny


@api_view(['POST'])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_screenshot(request):
    """上传执行截图，返回可访问 URL
    
    注意：此接口使用 Bearer Token 认证
    执行器通过 /api/token/ 获取 JWT Token 后调用此接口
    """
    file = request.FILES.get('file')
    if not file:
        return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)
    
    # 保存到 media/ui_screenshots/{日期}/
    date_dir = datetime.now().strftime('%Y%m%d')
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'ui_screenshots', date_dir)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名
    ext = os.path.splitext(file.name)[1] or '.png'
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, filename)
    
    with open(file_path, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)
    
    url = f"{settings.MEDIA_URL}ui_screenshots/{date_dir}/{filename}"
    return Response({'status': 'success', 'url': url}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_trace(request):
    """上传 Playwright Trace 文件，返回可访问 URL
    
    注意：此接口使用 Bearer Token 认证
    执行器执行完成后调用此接口上传 trace.zip 文件
    """
    file = request.FILES.get('file')
    if not file:
        return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)
    
    # 保存到 media/ui_traces/{日期}/
    date_dir = datetime.now().strftime('%Y%m%d')
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'ui_traces', date_dir)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名
    ext = os.path.splitext(file.name)[1] or '.zip'
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, filename)
    
    with open(file_path, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)
    
    # 返回相对路径（用于存储到数据库）和 URL（用于下载）
    relative_path = f"ui_traces/{date_dir}/{filename}"
    url = f"{settings.MEDIA_URL}{relative_path}"
    return Response({
        'status': 'success',
        'url': url,
        'path': relative_path
    }, status=status.HTTP_201_CREATED)
