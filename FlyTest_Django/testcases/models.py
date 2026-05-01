from django.db import IntegrityError, models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from projects.models import Project # 确保从正确的应用导入Project模型
import os


def _get_lowest_available_testcase_id():
    """
    获取当前最小可复用的测试用例 ID。
    规则：从 1 开始，删除后释放，再次创建时优先复用空缺。
    """
    expected_id = 1
    existing_ids = TestCase.objects.order_by("id").values_list("id", flat=True)
    for current_id in existing_ids.iterator():
        if current_id != expected_id:
            return expected_id
        expected_id += 1
    return expected_id


def testcase_screenshot_path(instance, filename):
    """
    生成测试用例截屏的文件路径
    路径格式: testcase_screenshots/{project_id}/{testcase_id}/{filename}
    """
    return f"testcase_screenshots/{instance.test_case.project.id}/{instance.test_case.id}/{filename}"


def testbug_attachment_path(instance, filename):
    return f"testbug_attachments/{instance.bug.project.id}/{instance.bug.id}/{instance.section}/{filename}"

class TestCase(models.Model):
    """
    用例模型
    """
    LEVEL_CHOICES = [
        ('P0', _('P0')),
        ('P1', _('P1')),
        ('P2', _('P2')),
        ('P3', _('P3')),
    ]

    TEST_TYPE_CHOICES = [
        ('smoke', _('冒烟测试')),
        ('functional', _('功能测试')),
        ('boundary', _('边界测试')),
        ('exception', _('异常测试')),
        ('permission', _('权限测试')),
        ('security', _('安全测试')),
        ('compatibility', _('兼容性测试')),
    ]

    REVIEW_STATUS_CHOICES = [
        ('pending_review', _('待审核')),
        ('approved', _('通过')),
        ('needs_optimization', _('优化')),
        ('optimization_pending_review', _('优化待审核')),
        ('unavailable', _('不可用')),
    ]

    EXECUTION_STATUS_CHOICES = [
        ('not_executed', _('Not Executed')),
        ('passed', _('Passed')),
        ('failed', _('Failed')),
        ('not_applicable', _('Not Applicable')),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='testcases',
        verbose_name=_('所属项目')
    )
    module = models.ForeignKey(
        'TestCaseModule',
        on_delete=models.PROTECT, # 有用例时不能删除模块
        null=False,  # 不允许为空
        blank=False, # 表单中必填
        related_name='testcases',
        verbose_name=_('所属模块')
    )
    name = models.CharField(_('用例名称'), max_length=255)
    precondition = models.TextField(_('前置描述'), blank=True, null=True)
    level = models.CharField(
        _('用例等级'),
        max_length=2,
        choices=LEVEL_CHOICES,
        default='P2' # 可以设置一个默认等级
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_testcases',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    notes = models.TextField(_('备注'), blank=True, null=True)
    screenshot = models.ImageField(
        _('截屏图片'),
        upload_to='testcase_screenshots/',
        blank=True,
        null=True,
        help_text=_('测试用例的截屏图片')
    )
    review_status = models.CharField(
        _('审核状态'),
        max_length=30,
        choices=REVIEW_STATUS_CHOICES,
        default='pending_review',
        blank=True,
        null=True,
    )
    test_type = models.CharField(
        _('测试类型'),
        max_length=20,
        choices=TEST_TYPE_CHOICES,
        default='functional',
        blank=True,
    )

    execution_status = models.CharField(
        _('Execution Status'),
        max_length=20,
        choices=EXECUTION_STATUS_CHOICES,
        default='not_executed',
        blank=True,
    )
    executed_at = models.DateTimeField(_('Execution Time'), null=True, blank=True)

    class Meta:
        verbose_name = _('用例')
        verbose_name_plural = _('用例')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def clean(self):
        self.name = str(self.name or "").strip()
        if not self.name:
            raise ValidationError(_("用例名称不能为空"))

        if self.module_id:
            duplicate_queryset = TestCase.objects.filter(module_id=self.module_id, name=self.name)
            if self.pk:
                duplicate_queryset = duplicate_queryset.exclude(pk=self.pk)
            if duplicate_queryset.exists():
                raise ValidationError(
                    {"name": _(f'模块“{self.module.name}”下已存在同名测试用例“{self.name}”')}
                )

    def save(self, *args, **kwargs):
        self.clean()
        if self.pk is not None:
            return super().save(*args, **kwargs)

        last_error = None
        for _ in range(5):
            try:
                with transaction.atomic():
                    self.pk = _get_lowest_available_testcase_id()
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                # 并发创建时如果抢到了同一个可用 ID，则重试分配。
                last_error = exc
                self.pk = None

        if last_error is not None:
            raise last_error

        return super().save(*args, **kwargs)

class TestCaseStep(models.Model):
    """
    用例步骤模型
    """
    test_case = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('所属用例')
    )
    step_number = models.PositiveIntegerField(_('步骤编号'))
    description = models.TextField(_('步骤描述'))
    expected_result = models.TextField(_('预期结果'))
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_testcase_steps',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('用例步骤')
        verbose_name_plural = _('用例步骤')
        ordering = ['test_case', 'step_number']
        unique_together = ('test_case', 'step_number') #确保同一用例下的步骤编号唯一

    def __str__(self):
        return f"{self.test_case.name} - Step {self.step_number}"


class TestCaseModule(models.Model):
    """
    用例模块模型，支持5级子模块
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='testcase_modules',
        verbose_name=_('所属项目')
    )
    name = models.CharField(_('模块名称'), max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('父模块')
    )
    level = models.PositiveSmallIntegerField(_('模块级别'), default=1)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_testcase_modules',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('用例模块')
        verbose_name_plural = _('用例模块')
        ordering = ['project', 'level', 'name']
        unique_together = ('project', 'parent', 'name')  # 确保同一父模块下的子模块名称唯一

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name

    def clean(self):
        """验证模块级别不超过5级"""
        if self.level > 5:
            raise ValidationError(_('模块级别不能超过5级'))

        # 验证父模块属于同一个项目
        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError(_('父模块必须属于同一个项目'))

        # 验证父模块的级别比当前模块低一级
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 1

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_all_descendant_ids(self):
        """
        获取当前模块及其所有子模块的ID列表（递归）
        """
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_descendant_ids())
        return ids


class TestCaseScreenshot(models.Model):
    """
    测试用例截屏模型 - 支持一个用例多张截屏
    """
    test_case = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='screenshots',
        verbose_name=_('测试用例')
    )
    screenshot = models.ImageField(
        _('截屏图片'),
        upload_to=testcase_screenshot_path,
        help_text=_('测试用例的截屏图片')
    )
    title = models.CharField(_('图片标题'), max_length=255, blank=True, null=True)
    description = models.TextField(_('图片描述'), blank=True, null=True)
    step_number = models.PositiveIntegerField(_('对应步骤'), blank=True, null=True)
    created_at = models.DateTimeField(_('上传时间'), auto_now_add=True)

    # MCP执行相关信息
    mcp_session_id = models.CharField(_('MCP会话ID'), max_length=255, blank=True, null=True)
    page_url = models.URLField(_('页面URL'), max_length=2000, blank=True, null=True)

    # 上传人信息
    uploader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_screenshots',
        verbose_name=_('上传人')
    )

    class Meta:
        verbose_name = _('测试用例截屏')
        verbose_name_plural = _('测试用例截屏')
        ordering = ['test_case', 'step_number', 'created_at']

    def __str__(self):
        if self.title:
            return f"{self.test_case.name} - {self.title}"
        elif self.step_number:
            return f"{self.test_case.name} - Step {self.step_number}"
        return f"{self.test_case.name} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    def delete(self, *args, **kwargs):
        """删除模型时同时删除文件"""
        if self.screenshot:
            if os.path.isfile(self.screenshot.path):
                os.remove(self.screenshot.path)
        super().delete(*args, **kwargs)


class TestSuite(models.Model):
    """
    测试套件模型 - 用于批量执行测试用例
    """
    name = models.CharField(_('套件名称'), max_length=255)
    description = models.TextField(_('套件描述'), blank=True, null=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='test_suites',
        verbose_name=_('所属项目')
    )
    testcases = models.ManyToManyField(
        TestCase,
        related_name='test_suites',
        verbose_name=_('测试用例'),
        blank=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('父套件')
    )
    level = models.PositiveSmallIntegerField(_('套件级别'), default=1)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_test_suites',
        verbose_name=_('创建人')
    )
    # 并发执行配置
    max_concurrent_tasks = models.PositiveSmallIntegerField(
        _('最大并发数'),
        default=1,
        help_text=_('同时执行的测试用例数量，1表示串行执行，建议值2-5')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('测试套件')
        verbose_name_plural = _('测试套件')
        ordering = ['-created_at']
        unique_together = ('project', 'parent', 'name')

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return f"{self.project.name} - {self.name}"

    def clean(self):
        if self.level > 5:
            raise ValidationError(_('套件级别不能超过5级'))

        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError(_('父套件必须属于同一个项目'))

        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 1

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_all_descendant_ids(self):
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_descendant_ids())
        return ids


class TestExecution(models.Model):
    """
    测试执行记录模型 - 记录测试套件的执行情况
    """
    STATUS_CHOICES = [
        ('pending', _('等待中')),
        ('running', _('执行中')),
        ('completed', _('已完成')),
        ('failed', _('失败')),
        ('cancelled', _('已取消')),
    ]
    
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name=_('测试套件')
    )
    status = models.CharField(
        _('执行状态'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    executor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='test_executions',
        verbose_name=_('执行人')
    )
    started_at = models.DateTimeField(_('开始时间'), null=True, blank=True)
    completed_at = models.DateTimeField(_('完成时间'), null=True, blank=True)
    total_count = models.PositiveIntegerField(_('总用例数'), default=0)
    passed_count = models.PositiveIntegerField(_('通过数'), default=0)
    failed_count = models.PositiveIntegerField(_('失败数'), default=0)
    skipped_count = models.PositiveIntegerField(_('跳过数'), default=0)
    error_count = models.PositiveIntegerField(_('错误数'), default=0)
    
    # Celery任务ID,用于追踪和取消任务
    celery_task_id = models.CharField(_('任务ID'), max_length=255, blank=True, null=True)

    # 是否为功能测试用例生成Playwright脚本
    generate_playwright_script = models.BooleanField(
        _('生成脚本'),
        default=False,
        help_text=_('执行功能测试用例时是否自动生成Playwright脚本')
    )

    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('测试执行记录')
        verbose_name_plural = _('测试执行记录')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.suite.name} - {self.get_status_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @property
    def duration(self):
        """计算执行时长(秒)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def pass_rate(self):
        """计算通过率"""
        if self.total_count > 0:
            return round((self.passed_count / self.total_count) * 100, 2)
        return 0.0


class TestCaseResult(models.Model):
    """
    测试用例执行结果模型 - 记录单个用例的执行结果
    """
    STATUS_CHOICES = [
        ('pending', _('等待中')),
        ('running', _('执行中')),
        ('pass', _('通过')),
        ('fail', _('失败')),
        ('skip', _('跳过')),
        ('error', _('错误')),
    ]
    
    execution = models.ForeignKey(
        TestExecution,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name=_('测试执行')
    )
    testcase = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='execution_results',
        verbose_name=_('测试用例')
    )
    status = models.CharField(
        _('执行状态'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(_('错误信息'), blank=True, null=True)
    stack_trace = models.TextField(_('堆栈跟踪'), blank=True, null=True)
    
    # 执行时间统计
    started_at = models.DateTimeField(_('开始时间'), null=True, blank=True)
    completed_at = models.DateTimeField(_('完成时间'), null=True, blank=True)
    execution_time = models.FloatField(_('执行耗时(秒)'), null=True, blank=True)
    
    # MCP相关信息
    mcp_session_id = models.CharField(_('MCP会话ID'), max_length=255, blank=True, null=True)
    
    # 截图信息(JSON格式存储截图路径列表)
    screenshots = models.JSONField(_('截图列表'), default=list, blank=True)
    
    # 执行日志
    execution_log = models.TextField(_('执行日志'), blank=True, null=True)
    
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('测试用例执行结果')
        verbose_name_plural = _('测试用例执行结果')
        ordering = ['execution', 'created_at']
        unique_together = ('execution', 'testcase')
    
    def __str__(self):
        return f"{self.testcase.name} - {self.get_status_display()}"
    
    @property
    def duration(self):
        """计算执行时长(秒)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return self.execution_time


class TestCaseAssignment(models.Model):
    """测试用例分配信息。"""

    testcase = models.OneToOneField(
        TestCase,
        on_delete=models.CASCADE,
        related_name="assignment",
        verbose_name=_("测试用例"),
    )
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        related_name="assigned_testcases",
        verbose_name=_("测试套件"),
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="testcase_assignments",
        verbose_name=_("执行人"),
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_testcase_assignments",
        verbose_name=_("分配人"),
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("测试用例分配")
        verbose_name_plural = _("测试用例分配")
        ordering = ["-updated_at"]

    def clean(self):
        if self.testcase.project_id != self.suite.project_id:
            raise ValidationError(_("测试套件必须与测试用例属于同一项目"))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.testcase.name} -> {self.assignee.username}"


class TestBug(models.Model):
    """测试套件下的缺陷管理，参考禅道 BUG 流转。"""

    STATUS_UNASSIGNED = "unassigned"
    STATUS_ASSIGNED = "assigned"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FIXED = "fixed"
    STATUS_PENDING_RETEST = "pending_retest"
    STATUS_CLOSED = "closed"
    STATUS_EXPIRED = "expired"

    SEVERITY_CHOICES = [
        ("1", _("1")),
        ("2", _("2")),
        ("3", _("3")),
        ("4", _("4")),
    ]

    PRIORITY_CHOICES = [
        ("1", _("1")),
        ("2", _("2")),
        ("3", _("3")),
        ("4", _("4")),
    ]

    TYPE_CHOICES = [
        ("codeerror", _("代码错误")),
        ("config", _("配置相关")),
        ("install", _("安装部署")),
        ("security", _("安全相关")),
        ("performance", _("性能问题")),
        ("standard", _("界面优化")),
        ("design", _("设计缺陷")),
        ("others", _("其他")),
    ]

    WORKFLOW_STATUS_CHOICES = [
        (STATUS_UNASSIGNED, _("未指派")),
        (STATUS_ASSIGNED, _("未确认")),
        (STATUS_CONFIRMED, _("已确认")),
        (STATUS_FIXED, _("已修复")),
        (STATUS_PENDING_RETEST, _("待复测")),
        (STATUS_CLOSED, _("已关闭")),
        (STATUS_EXPIRED, _("已过期")),
    ]

    LEGACY_STATUS_CHOICES = [
        ("active", _("激活中")),
        ("resolved", _("已解决")),
        ("closed", _("已关闭")),
    ]

    STATUS_CHOICES = LEGACY_STATUS_CHOICES + [
        (STATUS_UNASSIGNED, _("未指派")),
        (STATUS_ASSIGNED, _("未确认")),
        (STATUS_CONFIRMED, _("已确认")),
        (STATUS_FIXED, _("已修复")),
        (STATUS_PENDING_RETEST, _("待复测")),
        (STATUS_EXPIRED, _("已过期")),
    ]

    RESOLUTION_CHOICES = [
        ("", _("-")),
        ("fixed", _("已修复")),
        ("postponed", _("延期处理")),
        ("notrepro", _("无法重现")),
        ("external", _("外部原因")),
        ("duplicate", _("重复 Bug")),
        ("wontfix", _("不予修复")),
        ("bydesign", _("设计如此")),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="test_bugs",
        verbose_name=_("所属项目"),
    )
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        related_name="bugs",
        verbose_name=_("所属套件"),
    )
    testcase = models.ForeignKey(
        TestCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bugs",
        verbose_name=_("关联测试用例"),
    )
    related_testcases = models.ManyToManyField(
        TestCase,
        blank=True,
        related_name="related_bugs",
        verbose_name=_("关联测试用例列表"),
    )
    title = models.CharField(_("Bug标题"), max_length=255)
    steps = models.TextField(_("重现步骤"), blank=True, default="")
    expected_result = models.TextField(_("期望结果"), blank=True, default="")
    actual_result = models.TextField(_("实际结果"), blank=True, default="")
    bug_type = models.CharField(
        _("Bug类型"),
        max_length=20,
        choices=TYPE_CHOICES,
        default="codeerror",
    )
    severity = models.CharField(
        _("严重程度"),
        max_length=1,
        choices=SEVERITY_CHOICES,
        default="3",
    )
    priority = models.CharField(
        _("优先级"),
        max_length=1,
        choices=PRIORITY_CHOICES,
        default="3",
    )
    status = models.CharField(
        _("状态"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    resolution = models.CharField(
        _("解决方案"),
        max_length=20,
        choices=RESOLUTION_CHOICES,
        blank=True,
        default="",
    )
    keywords = models.CharField(_("关键词"), max_length=255, blank=True, default="")
    deadline = models.DateField(_("截止日期"), null=True, blank=True)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_test_bugs",
        verbose_name=_("指派给"),
    )
    assigned_users = models.ManyToManyField(
        User,
        blank=True,
        related_name="multi_assigned_test_bugs",
        verbose_name=_("指派成员"),
    )
    opened_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_test_bugs",
        verbose_name=_("由谁创建"),
    )
    opened_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    assigned_at = models.DateTimeField(_("指派时间"), null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_test_bugs",
        verbose_name=_("由谁解决"),
    )
    resolved_at = models.DateTimeField(_("解决时间"), null=True, blank=True)
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_test_bugs",
        verbose_name=_("由谁关闭"),
    )
    closed_at = models.DateTimeField(_("关闭时间"), null=True, blank=True)
    activated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activated_test_bugs",
        verbose_name=_("由谁激活"),
    )
    activated_at = models.DateTimeField(_("激活时间"), null=True, blank=True)
    activated_count = models.PositiveIntegerField(_("激活次数"), default=0)
    solution = models.TextField(_("处理备注"), blank=True, default="")
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("测试Bug")
        verbose_name_plural = _("测试Bug")
        ordering = ["-id"]

    def clean(self):
        if self.suite_id and self.project_id and self.suite.project_id != self.project_id:
            raise ValidationError(_("测试套件必须属于当前项目"))

        if self.testcase_id:
            if self.project_id and self.testcase.project_id != self.project_id:
                raise ValidationError(_("测试用例必须属于当前项目"))
            if self.suite_id and not self.suite.testcases.filter(id=self.testcase_id).exists():
                raise ValidationError(_("关联测试用例必须已分配到当前测试套件"))

        if self.pk and self.suite_id:
            invalid_related_ids = list(
                self.related_testcases.exclude(project_id=self.project_id).values_list("id", flat=True)
            )
            if invalid_related_ids:
                raise ValidationError(_("关联测试用例必须属于当前项目"))

            suite_testcase_ids = set(self.suite.testcases.values_list("id", flat=True))
            if suite_testcase_ids:
                missing_suite_ids = [
                    testcase_id
                    for testcase_id in self.related_testcases.values_list("id", flat=True)
                    if testcase_id not in suite_testcase_ids
                ]
                if missing_suite_ids:
                    raise ValidationError(_("只能关联当前套件中的测试用例"))

    def has_assignees(self):
        if self.assigned_to_id:
            return True
        if not self.pk:
            return False
        return self.assigned_users.exists()

    @classmethod
    def normalize_status_value(cls, status, assigned_to_id=None, has_assignees=None):
        if has_assignees is None:
            has_assignees = bool(assigned_to_id)

        if status == "active":
            return cls.STATUS_ASSIGNED if has_assignees else cls.STATUS_UNASSIGNED
        if status == "resolved":
            return cls.STATUS_PENDING_RETEST
        if status == "closed":
            return cls.STATUS_CLOSED
        if status == cls.STATUS_UNASSIGNED:
            return cls.STATUS_ASSIGNED if has_assignees else cls.STATUS_UNASSIGNED
        if status == cls.STATUS_ASSIGNED:
            return cls.STATUS_ASSIGNED if has_assignees else cls.STATUS_UNASSIGNED
        if status in {choice[0] for choice in cls.STATUS_CHOICES}:
            return status
        return cls.STATUS_ASSIGNED if has_assignees else cls.STATUS_UNASSIGNED

    def get_effective_status(self):
        normalized_status = self.normalize_status_value(
            self.status,
            self.assigned_to_id,
            self.has_assignees(),
        )
        if normalized_status != self.STATUS_CLOSED and self.deadline and self.deadline < timezone.localdate():
            return self.STATUS_EXPIRED
        return normalized_status

    def get_effective_status_display(self):
        effective_status = self.get_effective_status()
        return dict(self.WORKFLOW_STATUS_CHOICES).get(effective_status, effective_status)

    def save(self, *args, **kwargs):
        self.clean()
        self.status = self.normalize_status_value(self.status, self.assigned_to_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"BUG#{self.pk} {self.title}"


class TestBugAttachment(models.Model):
    SECTION_CHOICES = [
        ("steps", _("重现步骤")),
        ("expected_result", _("期望结果")),
        ("actual_result", _("实际结果")),
    ]

    TYPE_CHOICES = [
        ("image", _("图片")),
        ("video", _("视频")),
        ("file", _("文件")),
    ]

    bug = models.ForeignKey(
        TestBug,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("所属Bug"),
    )
    section = models.CharField(_("所属区域"), max_length=30, choices=SECTION_CHOICES)
    attachment = models.FileField(_("附件"), upload_to=testbug_attachment_path)
    original_name = models.CharField(_("原始文件名"), max_length=255, blank=True, default="")
    file_type = models.CharField(_("附件类型"), max_length=20, choices=TYPE_CHOICES, default="file")
    content_type = models.CharField(_("内容类型"), max_length=120, blank=True, default="")
    file_size = models.PositiveBigIntegerField(_("文件大小"), default=0)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_test_bug_attachments",
        verbose_name=_("上传人"),
    )
    created_at = models.DateTimeField(_("上传时间"), auto_now_add=True)

    class Meta:
        verbose_name = _("测试Bug附件")
        verbose_name_plural = _("测试Bug附件")
        ordering = ["section", "-created_at", "-id"]

    def __str__(self):
        file_name = self.original_name or os.path.basename(self.attachment.name)
        return f"{self.bug_id} - {self.section} - {file_name}"

    def delete(self, *args, **kwargs):
        if self.attachment and os.path.isfile(self.attachment.path):
            os.remove(self.attachment.path)
        super().delete(*args, **kwargs)


class TestBugActivity(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_ASSIGN = "assign"
    ACTION_CONFIRM = "confirm"
    ACTION_FIX = "fix"
    ACTION_RESOLVE = "resolve"
    ACTION_ACTIVATE = "activate"
    ACTION_CLOSE = "close"
    ACTION_STATUS_CHANGE = "status_change"
    ACTION_UPLOAD_ATTACHMENT = "upload_attachment"
    ACTION_DELETE_ATTACHMENT = "delete_attachment"

    ACTION_CHOICES = [
        (ACTION_CREATE, _("新建")),
        (ACTION_UPDATE, _("编辑")),
        (ACTION_ASSIGN, _("指派")),
        (ACTION_CONFIRM, _("确认")),
        (ACTION_FIX, _("修复")),
        (ACTION_RESOLVE, _("提交复测")),
        (ACTION_ACTIVATE, _("激活")),
        (ACTION_CLOSE, _("关闭")),
        (ACTION_STATUS_CHANGE, _("状态变更")),
        (ACTION_UPLOAD_ATTACHMENT, _("上传附件")),
        (ACTION_DELETE_ATTACHMENT, _("删除附件")),
    ]

    bug = models.ForeignKey(
        TestBug,
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name=_("所属Bug"),
    )
    action = models.CharField(_("操作类型"), max_length=40, choices=ACTION_CHOICES)
    content = models.TextField(_("操作内容"), blank=True, default="")
    metadata = models.JSONField(_("附加数据"), blank=True, default=dict)
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operated_test_bug_activities",
        verbose_name=_("操作人"),
    )
    created_at = models.DateTimeField(_("操作时间"), auto_now_add=True)

    class Meta:
        verbose_name = _("测试Bug操作历史")
        verbose_name_plural = _("测试Bug操作历史")
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"BUG#{self.bug_id} {self.get_action_display()} {self.created_at:%Y-%m-%d %H:%M:%S}"
