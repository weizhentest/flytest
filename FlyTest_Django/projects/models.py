from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _


class Project(models.Model):
    name = models.CharField(_('项目名称'), max_length=100, unique=True)
    description = models.TextField(_('项目描述'), blank=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects',
        verbose_name=_('创建人'),
    )
    is_deleted = models.BooleanField(_('是否已删除'), default=False)
    deleted_at = models.DateTimeField(_('删除时间'), null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_projects',
        verbose_name=_('删除人'),
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('项目')
        verbose_name_plural = _('项目')
        ordering = ['id']

    def __str__(self):
        return self.name


class ProjectDeletionRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_RESTORED = 'restored'

    STATUS_CHOICES = (
        (STATUS_PENDING, _('待审核')),
        (STATUS_APPROVED, _('已删除')),
        (STATUS_REJECTED, _('已驳回')),
        (STATUS_RESTORED, _('已恢复')),
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deletion_requests',
        verbose_name=_('项目'),
    )
    project_name = models.CharField(_('项目名称快照'), max_length=100)
    project_display_id = models.PositiveIntegerField(_('项目ID快照'))
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_deletion_requests',
        verbose_name=_('申请人'),
    )
    requested_by_name = models.CharField(_('申请人姓名'), max_length=100, blank=True, default='')
    request_note = models.TextField(_('申请说明'), blank=True, default='')
    status = models.CharField(_('状态'), max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_project_deletion_requests',
        verbose_name=_('审核人'),
    )
    reviewed_by_name = models.CharField(_('审核人姓名'), max_length=100, blank=True, default='')
    review_note = models.TextField(_('审核备注'), blank=True, default='')
    requested_at = models.DateTimeField(_('申请时间'), auto_now_add=True)
    reviewed_at = models.DateTimeField(_('审核时间'), null=True, blank=True)
    deleted_at = models.DateTimeField(_('删除时间'), null=True, blank=True)
    restored_at = models.DateTimeField(_('恢复时间'), null=True, blank=True)
    restored_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restored_project_deletion_requests',
        verbose_name=_('恢复人'),
    )
    restored_by_name = models.CharField(_('恢复人姓名'), max_length=100, blank=True, default='')

    class Meta:
        verbose_name = _('项目删除记录')
        verbose_name_plural = _('项目删除记录')
        ordering = ['-requested_at']

    def __str__(self):
        return f'{self.project_name} - {self.status}'


class ProjectMember(models.Model):
    ROLE_CHOICES = (
        ('owner', _('拥有者')),
        ('admin', _('管理员')),
        ('member', _('成员')),
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('项目'),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name=_('用户'),
    )
    role = models.CharField(
        _('角色'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='member',
    )
    joined_at = models.DateTimeField(_('加入时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('项目成员')
        verbose_name_plural = _('项目成员')
        unique_together = ('project', 'user')
        ordering = ['project', 'role', 'joined_at']

    def __str__(self):
        return f'{self.user.username} - {self.project.name} ({self.get_role_display()})'
