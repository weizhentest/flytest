# 导入 Django ORM 基类。
from django.db import models

# 导入内置用户模型。
from django.contrib.auth.models import User

# 导入 i18n 翻译工具。
from django.utils.translation import gettext_lazy as _


class Project(models.Model):
    """
    项目模型，包含项目的基本信息
    """
    # 项目名称（全局唯一），用于业务侧主识别字段。
    name = models.CharField(_('项目名称'), max_length=100, unique=True)
    # 项目描述，可为空。
    description = models.TextField(_('项目描述'), blank=True)
    # 创建人，用户删除后置空以保留项目历史记录。
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects',
        verbose_name=_('创建人')
    )
    # 项目创建时间。
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    # 项目最后更新时间。
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('项目')
        verbose_name_plural = _('项目')
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ProjectCredential(models.Model):
    """
    项目凭据模型，存储项目的系统访问信息
    一个项目可以有多个凭据，用于不同角色的登录
    """
    # 所属项目。
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='credentials',
        verbose_name=_('项目')
    )
    # 被测系统访问地址。
    system_url = models.URLField(_('项目地址'), max_length=255, blank=True, help_text='系统访问地址（如 https://test.example.com）')
    # 登录用户名。
    username = models.CharField(_('用户名'), max_length=100, blank=True, help_text='登录账号')
    # 登录密码（当前为明文存储，建议生产环境接入加密/密文方案）。
    password = models.CharField(_('密码'), max_length=255, blank=True, help_text='登录密码')
    # 凭据角色标签（如管理员/审核员）。
    user_role = models.CharField(_('角色'), max_length=50, blank=True, help_text='如"管理员"、"普通用户"、"审核员"等')
    # 凭据创建时间。
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('项目凭据')
        verbose_name_plural = _('项目凭据')
        ordering = ['project', 'user_role']

    def __str__(self):
        return f"{self.project.name} - {self.user_role or self.username}"


class ProjectMember(models.Model):
    """
    项目成员关系模型，定义用户与项目的关系
    """
    ROLE_CHOICES = (
        ('owner', _('拥有者')),  # 项目最高权限，允许转移拥有者和删除项目。
        ('admin', _('管理员')),  # 管理权限，可维护成员和项目配置。
        ('member', _('成员')),  # 普通成员，主要用于访问与协作。
    )

    # 关联项目。
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('项目')
    )
    # 关联用户。
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name=_('用户')
    )
    # 用户在项目中的角色。
    role = models.CharField(
        _('角色'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='member'
    )
    # 加入项目时间。
    joined_at = models.DateTimeField(_('加入时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('项目成员')
        verbose_name_plural = _('项目成员')
        unique_together = ('project', 'user')  # 确保一个用户在一个项目中只有一个角色
        ordering = ['project', 'role', 'joined_at']

    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.get_role_display()})"
