from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from projects.models import Project


class ApiCollection(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_collections",
        verbose_name=_("所属项目"),
    )
    name = models.CharField(_("集合名称"), max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("父集合"),
    )
    order = models.PositiveIntegerField(_("排序"), default=0)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_collections",
        verbose_name=_("创建人"),
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 集合")
        verbose_name_plural = _("API 集合")
        ordering = ["order", "created_at"]
        unique_together = ("project", "parent", "name")
        db_table = "api_automation_collection"

    def __str__(self) -> str:
        return f"{self.project.name} - {self.name}"

    def clean(self):
        if self.parent and self.parent.project_id != self.project_id:
            raise ValueError("父集合必须属于同一个项目")


class ApiRequest(models.Model):
    METHOD_CHOICES = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
        ("HEAD", "HEAD"),
        ("OPTIONS", "OPTIONS"),
    ]

    BODY_TYPE_CHOICES = [
        ("none", "none"),
        ("json", "json"),
        ("form", "form"),
        ("raw", "raw"),
    ]

    collection = models.ForeignKey(
        ApiCollection,
        on_delete=models.CASCADE,
        related_name="requests",
        verbose_name=_("所属集合"),
    )
    name = models.CharField(_("请求名称"), max_length=120)
    description = models.TextField(_("请求描述"), blank=True, null=True)
    method = models.CharField(_("请求方法"), max_length=10, choices=METHOD_CHOICES, default="GET")
    url = models.TextField(_("请求地址"))
    headers = models.JSONField(_("请求头"), default=dict, blank=True)
    params = models.JSONField(_("查询参数"), default=dict, blank=True)
    body_type = models.CharField(_("请求体类型"), max_length=20, choices=BODY_TYPE_CHOICES, default="none")
    body = models.JSONField(_("请求体"), default=dict, blank=True)
    assertions = models.JSONField(_("断言规则"), default=list, blank=True)
    timeout_ms = models.PositiveIntegerField(_("超时时间(ms)"), default=30000)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_requests",
        verbose_name=_("创建人"),
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 请求")
        verbose_name_plural = _("API 请求")
        ordering = ["order", "created_at"]
        db_table = "api_automation_request"

    def __str__(self) -> str:
        return f"{self.collection.name} - {self.name}"


class ApiEnvironment(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_environments",
        verbose_name=_("所属项目"),
    )
    name = models.CharField(_("环境名称"), max_length=100)
    base_url = models.CharField(_("基础地址"), max_length=500, blank=True, default="")
    common_headers = models.JSONField(_("公共请求头"), default=dict, blank=True)
    variables = models.JSONField(_("环境变量"), default=dict, blank=True)
    timeout_ms = models.PositiveIntegerField(_("默认超时(ms)"), default=30000)
    is_default = models.BooleanField(_("是否默认"), default=False)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_environments",
        verbose_name=_("创建人"),
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 环境")
        verbose_name_plural = _("API 环境")
        ordering = ["project", "-is_default", "name"]
        unique_together = ("project", "name")
        db_table = "api_automation_environment"

    def __str__(self) -> str:
        return f"{self.project.name} - {self.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            ApiEnvironment.objects.filter(project=self.project, is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )


class ApiExecutionRecord(models.Model):
    STATUS_CHOICES = [
        ("success", "success"),
        ("failed", "failed"),
        ("error", "error"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_execution_records",
        verbose_name=_("所属项目"),
    )
    request = models.ForeignKey(
        ApiRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_records",
        verbose_name=_("所属请求"),
    )
    environment = models.ForeignKey(
        ApiEnvironment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_records",
        verbose_name=_("执行环境"),
    )
    request_name = models.CharField(_("请求名称"), max_length=120)
    method = models.CharField(_("请求方法"), max_length=10)
    url = models.TextField(_("最终地址"))
    status = models.CharField(_("执行状态"), max_length=20, choices=STATUS_CHOICES, default="success")
    passed = models.BooleanField(_("是否通过"), default=False)
    status_code = models.IntegerField(_("响应状态码"), null=True, blank=True)
    response_time = models.FloatField(_("响应时间(ms)"), null=True, blank=True)
    request_snapshot = models.JSONField(_("请求快照"), default=dict, blank=True)
    response_snapshot = models.JSONField(_("响应快照"), default=dict, blank=True)
    assertions_results = models.JSONField(_("断言结果"), default=list, blank=True)
    error_message = models.TextField(_("错误信息"), blank=True, null=True)
    executor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_execution_records",
        verbose_name=_("执行人"),
    )
    created_at = models.DateTimeField(_("执行时间"), auto_now_add=True)

    class Meta:
        verbose_name = _("API 执行记录")
        verbose_name_plural = _("API 执行记录")
        ordering = ["-created_at"]
        db_table = "api_automation_execution_record"

    def __str__(self) -> str:
        return f"{self.request_name} - {self.created_at}"


class ApiTestCase(models.Model):
    STATUS_CHOICES = [
        ("draft", "draft"),
        ("ready", "ready"),
        ("disabled", "disabled"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_test_cases",
        verbose_name=_("所属项目"),
    )
    request = models.ForeignKey(
        ApiRequest,
        on_delete=models.CASCADE,
        related_name="test_cases",
        verbose_name=_("关联请求"),
    )
    name = models.CharField(_("测试用例名称"), max_length=160)
    description = models.TextField(_("测试用例描述"), blank=True, null=True)
    status = models.CharField(_("状态"), max_length=20, choices=STATUS_CHOICES, default="draft")
    tags = models.JSONField(_("标签"), default=list, blank=True)
    script = models.JSONField(_("接口脚本"), default=dict, blank=True)
    assertions = models.JSONField(_("断言规则"), default=list, blank=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_test_cases",
        verbose_name=_("创建人"),
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 测试用例")
        verbose_name_plural = _("API 测试用例")
        ordering = ["-created_at"]
        db_table = "api_automation_test_case"

    def __str__(self) -> str:
        return f"{self.request.name} - {self.name}"
