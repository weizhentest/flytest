from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.serializers import UserDetailSerializer
from flytest_django.viewsets import BaseModelViewSet

from .models import Project, ProjectDeletionRequest, ProjectMember
from .permissions import HasProjectMemberPermission, IsProjectAdmin, IsProjectMember
from .serializers import (
    ProjectDeletionRequestSerializer,
    ProjectDetailSerializer,
    ProjectMemberCreateSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
)


class ProjectViewSet(BaseModelViewSet):
    queryset = Project.objects.filter(is_deleted=False)
    serializer_class = ProjectSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_queryset(self):
        user = self.request.user
        queryset = Project.objects.filter(is_deleted=False)
        if user.is_superuser:
            return queryset
        return queryset.filter(members__user=user).distinct()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProjectDetailSerializer
        if self.action == 'deletion_requests':
            return ProjectDeletionRequestSerializer
        return ProjectSerializer

    def get_permissions(self):
        if self.action == 'members':
            return [IsAuthenticated(), IsProjectMember()]
        if self.action in ['add_member', 'remove_member', 'update_member_role']:
            return [IsAuthenticated(), IsProjectAdmin()]
        if self.action == 'statistics':
            return [IsAuthenticated(), IsProjectMember()]
        if self.action in ['deletion_requests', 'approve_deletion_request', 'reject_deletion_request', 'restore_deletion_request']:
            return [IsAuthenticated()]

        base_permissions = super().get_permissions()
        if self.action in ['update', 'partial_update', 'destroy']:
            return base_permissions + [IsProjectAdmin()]
        if self.action == 'retrieve':
            return base_permissions + [IsProjectMember()]
        return base_permissions

    def perform_create(self, serializer):
        with transaction.atomic():
            project = serializer.save(creator=self.request.user)
            ProjectMember.objects.create(project=project, user=self.request.user, role='owner')

            platform_admins = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True), is_active=True)
            for admin in platform_admins:
                if admin != self.request.user:
                    ProjectMember.objects.get_or_create(
                        project=project,
                        user=admin,
                        defaults={'role': 'admin'},
                    )

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if project.is_deleted:
            return Response({'error': '该项目已删除'}, status=status.HTTP_400_BAD_REQUEST)

        existing = ProjectDeletionRequest.objects.filter(
            project=project,
            status=ProjectDeletionRequest.STATUS_PENDING,
        ).first()
        if existing:
            return Response({'error': '该项目已有待审核的删除申请'}, status=status.HTTP_400_BAD_REQUEST)

        profile = getattr(request.user, 'profile', None)
        requester_name = getattr(profile, 'real_name', '') or request.user.username
        deletion_request = ProjectDeletionRequest.objects.create(
            project=project,
            project_name=project.name,
            project_display_id=project.id,
            requested_by=request.user,
            requested_by_name=requester_name,
            request_note=(request.data or {}).get('note', ''),
        )
        serializer = ProjectDeletionRequestSerializer(deletion_request)
        return Response(
            {'message': '删除申请已提交，等待管理员审核', 'data': serializer.data},
            status=status.HTTP_202_ACCEPTED,
        )

    def _ensure_system_admin(self, request):
        return bool(request.user and (request.user.is_superuser or request.user.is_staff))

    def _get_deletion_request(self, request_id):
        return get_object_or_404(ProjectDeletionRequest, pk=request_id)

    @action(detail=False, methods=['get'], url_path='deletion-requests')
    def deletion_requests(self, request):
        if not self._ensure_system_admin(request):
            return Response({'error': '仅管理员可查看删除记录'}, status=status.HTTP_403_FORBIDDEN)

        queryset = ProjectDeletionRequest.objects.select_related(
            'project', 'requested_by', 'reviewed_by', 'restored_by'
        ).all()
        serializer = ProjectDeletionRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path=r'deletion-requests/(?P<request_id>\d+)/approve')
    def approve_deletion_request(self, request, request_id=None):
        if not self._ensure_system_admin(request):
            return Response({'error': '仅管理员可审核删除申请'}, status=status.HTTP_403_FORBIDDEN)

        deletion_request = self._get_deletion_request(request_id)
        if deletion_request.status != ProjectDeletionRequest.STATUS_PENDING:
            return Response({'error': '当前申请不是待审核状态'}, status=status.HTTP_400_BAD_REQUEST)
        if not deletion_request.project_id:
            return Response({'error': '项目不存在，无法执行删除'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        profile = getattr(request.user, 'profile', None)
        reviewer_name = getattr(profile, 'real_name', '') or request.user.username
        review_note = (request.data or {}).get('review_note', '')

        with transaction.atomic():
            project = deletion_request.project
            project.is_deleted = True
            project.deleted_at = now
            project.deleted_by = deletion_request.requested_by
            project.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

            deletion_request.status = ProjectDeletionRequest.STATUS_APPROVED
            deletion_request.reviewed_by = request.user
            deletion_request.reviewed_by_name = reviewer_name
            deletion_request.review_note = review_note
            deletion_request.reviewed_at = now
            deletion_request.deleted_at = now
            deletion_request.save(
                update_fields=[
                    'status',
                    'reviewed_by',
                    'reviewed_by_name',
                    'review_note',
                    'reviewed_at',
                    'deleted_at',
                ]
            )

        serializer = ProjectDeletionRequestSerializer(deletion_request)
        return Response({'message': '项目删除已审核通过', 'data': serializer.data})

    @action(detail=False, methods=['post'], url_path=r'deletion-requests/(?P<request_id>\d+)/reject')
    def reject_deletion_request(self, request, request_id=None):
        if not self._ensure_system_admin(request):
            return Response({'error': '仅管理员可审核删除申请'}, status=status.HTTP_403_FORBIDDEN)

        deletion_request = self._get_deletion_request(request_id)
        if deletion_request.status != ProjectDeletionRequest.STATUS_PENDING:
            return Response({'error': '当前申请不是待审核状态'}, status=status.HTTP_400_BAD_REQUEST)

        profile = getattr(request.user, 'profile', None)
        reviewer_name = getattr(profile, 'real_name', '') or request.user.username
        deletion_request.status = ProjectDeletionRequest.STATUS_REJECTED
        deletion_request.reviewed_by = request.user
        deletion_request.reviewed_by_name = reviewer_name
        deletion_request.review_note = (request.data or {}).get('review_note', '')
        deletion_request.reviewed_at = timezone.now()
        deletion_request.save(
            update_fields=['status', 'reviewed_by', 'reviewed_by_name', 'review_note', 'reviewed_at']
        )

        serializer = ProjectDeletionRequestSerializer(deletion_request)
        return Response({'message': '项目删除申请已驳回', 'data': serializer.data})

    @action(detail=False, methods=['post'], url_path=r'deletion-requests/(?P<request_id>\d+)/restore')
    def restore_deletion_request(self, request, request_id=None):
        if not self._ensure_system_admin(request):
            return Response({'error': '仅管理员可恢复项目'}, status=status.HTTP_403_FORBIDDEN)

        deletion_request = self._get_deletion_request(request_id)
        if deletion_request.status != ProjectDeletionRequest.STATUS_APPROVED:
            return Response({'error': '仅已删除的项目支持恢复'}, status=status.HTTP_400_BAD_REQUEST)
        if not deletion_request.project_id:
            return Response({'error': '项目不存在，无法恢复'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        profile = getattr(request.user, 'profile', None)
        restorer_name = getattr(profile, 'real_name', '') or request.user.username

        with transaction.atomic():
            project = deletion_request.project
            project.is_deleted = False
            project.deleted_at = None
            project.deleted_by = None
            project.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

            deletion_request.status = ProjectDeletionRequest.STATUS_RESTORED
            deletion_request.restored_at = now
            deletion_request.restored_by = request.user
            deletion_request.restored_by_name = restorer_name
            deletion_request.save(
                update_fields=['status', 'restored_at', 'restored_by', 'restored_by_name']
            )

        serializer = ProjectDeletionRequestSerializer(deletion_request)
        return Response({'message': '项目已恢复', 'data': serializer.data})

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        project = self.get_object()
        members = project.members.all()

        page = self.paginate_queryset(members)
        if page is not None:
            serializer = ProjectMemberSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProjectMemberSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberCreateSerializer(data=request.data, context={'project': project})

        if serializer.is_valid():
            member = serializer.save()
            member_serializer = ProjectMemberSerializer(member)
            return Response(member_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def remove_member(self, request, pk=None):
        project = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response({'error': '必须提供用户ID'}, status=status.HTTP_400_BAD_REQUEST)

        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)
        if member.role == 'owner' and not request.user.is_superuser:
            return Response({'error': '不能移除项目拥有者'}, status=status.HTTP_403_FORBIDDEN)
        if member.user == request.user and not request.user.is_superuser:
            return Response({'error': '不能移除自己'}, status=status.HTTP_403_FORBIDDEN)

        member.delete()
        return Response({'message': '成员已成功移除'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def update_member_role(self, request, pk=None):
        project = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role')

        if not user_id or not role:
            return Response({'error': '必须提供用户ID和角色'}, status=status.HTTP_400_BAD_REQUEST)
        if role not in [r[0] for r in ProjectMember.ROLE_CHOICES]:
            return Response({'error': '无效的角色'}, status=status.HTTP_400_BAD_REQUEST)

        member = get_object_or_404(ProjectMember, project=project, user_id=user_id)
        if member.role == 'owner' and not (
            request.user.is_superuser
            or ProjectMember.objects.filter(project=project, user=request.user, role='owner').exists()
        ):
            return Response({'error': '只有项目拥有者或超级管理员可以修改拥有者角色'}, status=status.HTTP_403_FORBIDDEN)
        if member.user == request.user and not request.user.is_superuser:
            return Response({'error': '不能修改自己的角色'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            if role == 'owner':
                current_owners = ProjectMember.objects.filter(project=project, role='owner')
                for owner in current_owners.exclude(user_id=int(user_id)):
                    owner.role = 'admin'
                    owner.save(update_fields=['role'])

            member.role = role
            member.save(update_fields=['role'])

        serializer = ProjectMemberSerializer(member)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        project = self.get_object()

        from mcp_tools.models import RemoteMCPConfig
        from skills.models import Skill
        from testcases.models import TestCase, TestExecution
        from ui_automation.models import UiExecutionRecord, UiTestCase

        testcase_stats = TestCase.objects.filter(project=project).aggregate(
            total=Count('id'),
            pending_review=Count('id', filter=Q(review_status='pending_review')),
            approved=Count('id', filter=Q(review_status='approved')),
            needs_optimization=Count('id', filter=Q(review_status='needs_optimization')),
            optimization_pending_review=Count('id', filter=Q(review_status='optimization_pending_review')),
            unavailable=Count('id', filter=Q(review_status='unavailable')),
        )

        executions = TestExecution.objects.filter(suite__project=project)
        execution_stats = executions.aggregate(
            total_executions=Count('id'),
            total_passed=Count('id', filter=Q(status='completed')),
            total_failed=Count('id', filter=Q(status='failed')),
            total_cancelled=Count('id', filter=Q(status='cancelled')),
        )
        execution_result_totals = executions.aggregate(
            total_passed_cases=Sum('passed_count'),
            total_failed_cases=Sum('failed_count'),
            total_skipped_cases=Sum('skipped_count'),
            total_error_cases=Sum('error_count'),
            total_cases=Sum('total_count'),
        )

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        daily_stats_7d = []
        for i in range(7):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_executions = executions.filter(created_at__gte=day_start, created_at__lt=day_end)
            day_agg = day_executions.aggregate(count=Count('id'), passed=Sum('passed_count'), failed=Sum('failed_count'))
            daily_stats_7d.append(
                {
                    'date': day_start.strftime('%Y-%m-%d'),
                    'execution_count': day_agg['count'] or 0,
                    'passed': day_agg['passed'] or 0,
                    'failed': day_agg['failed'] or 0,
                }
            )
        daily_stats_7d.reverse()

        stats_30d = executions.filter(created_at__gte=thirty_days_ago).aggregate(
            execution_count=Count('id'),
            passed=Sum('passed_count'),
            failed=Sum('failed_count'),
        )

        mcp_stats = {
            'total': RemoteMCPConfig.objects.count(),
            'active': RemoteMCPConfig.objects.filter(is_active=True).count(),
        }
        skill_stats = {
            'total': Skill.objects.count(),
            'active': Skill.objects.filter(is_active=True).count(),
        }

        ui_testcases = UiTestCase.objects.filter(project=project)
        ui_executions = UiExecutionRecord.objects.filter(test_case__project=project)
        ui_automation_stats = {
            'total_cases': ui_testcases.count(),
            'total_executions': ui_executions.count(),
            'by_status': {
                'success': ui_executions.filter(status=2).count(),
                'failed': ui_executions.filter(status=3).count(),
                'cancelled': ui_executions.filter(status=4).count(),
            },
        }

        response_data = {
            'project': {'id': project.id, 'name': project.name},
            'testcases': {
                'total': testcase_stats['total'],
                'by_review_status': {
                    'pending_review': testcase_stats['pending_review'],
                    'approved': testcase_stats['approved'],
                    'needs_optimization': testcase_stats['needs_optimization'],
                    'optimization_pending_review': testcase_stats['optimization_pending_review'],
                    'unavailable': testcase_stats['unavailable'],
                },
            },
            'executions': {
                'total_executions': execution_stats['total_executions'],
                'by_status': {
                    'completed': execution_stats['total_passed'],
                    'failed': execution_stats['total_failed'],
                    'cancelled': execution_stats['total_cancelled'],
                },
                'case_results': {
                    'total': execution_result_totals['total_cases'] or 0,
                    'passed': execution_result_totals['total_passed_cases'] or 0,
                    'failed': execution_result_totals['total_failed_cases'] or 0,
                    'skipped': execution_result_totals['total_skipped_cases'] or 0,
                    'error': execution_result_totals['total_error_cases'] or 0,
                },
            },
            'execution_trend': {
                'daily_7d': daily_stats_7d,
                'summary_30d': {
                    'execution_count': stats_30d['execution_count'] or 0,
                    'passed': stats_30d['passed'] or 0,
                    'failed': stats_30d['failed'] or 0,
                },
            },
            'mcp': mcp_stats,
            'skills': skill_stats,
            'ui_automation': ui_automation_stats,
        }

        return Response(response_data)
