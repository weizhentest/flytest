from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from projects.models import Project


def api_import_job_source_upload_path(instance, filename):
    project_id = instance.project_id or "unknown"
    sanitized_name = Path(filename).name or "document"
    return f"api_import_jobs/{project_id}/{uuid4().hex}_{sanitized_name}"


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


class ApiRequestSpec(models.Model):
    BODY_MODE_CHOICES = [
        ("none", "none"),
        ("json", "json"),
        ("form", "form"),
        ("urlencoded", "urlencoded"),
        ("multipart", "multipart"),
        ("raw", "raw"),
        ("xml", "xml"),
        ("graphql", "graphql"),
        ("binary", "binary"),
    ]

    request = models.OneToOneField(
        ApiRequest,
        on_delete=models.CASCADE,
        related_name="request_spec",
        verbose_name=_("请求规格"),
    )
    method = models.CharField(_("请求方法"), max_length=10, default="GET")
    url = models.TextField(_("请求地址"))
    body_mode = models.CharField(_("请求体模式"), max_length=20, choices=BODY_MODE_CHOICES, default="none")
    body_json = models.JSONField(_("JSON 请求体"), default=dict, blank=True)
    raw_text = models.TextField(_("原始文本请求体"), blank=True, default="")
    xml_text = models.TextField(_("XML 请求体"), blank=True, default="")
    binary_base64 = models.TextField(_("二进制 Base64"), blank=True, default="")
    graphql_query = models.TextField(_("GraphQL Query"), blank=True, default="")
    graphql_operation_name = models.CharField(_("GraphQL Operation"), max_length=120, blank=True, default="")
    graphql_variables = models.JSONField(_("GraphQL Variables"), default=dict, blank=True)
    timeout_ms = models.PositiveIntegerField(_("超时时间(ms)"), default=30000)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 请求规格")
        verbose_name_plural = _("API 请求规格")
        db_table = "api_automation_request_spec"

    def __str__(self) -> str:
        return f"{self.request.name} - spec"


class ApiRequestFieldSpec(models.Model):
    FIELD_KIND_CHOICES = [
        ("header", "header"),
        ("query", "query"),
        ("cookie", "cookie"),
        ("form", "form"),
        ("multipart_text", "multipart_text"),
    ]

    request_spec = models.ForeignKey(
        ApiRequestSpec,
        on_delete=models.CASCADE,
        related_name="field_specs",
        verbose_name=_("所属请求规格"),
    )
    field_kind = models.CharField(_("字段类型"), max_length=30, choices=FIELD_KIND_CHOICES)
    name = models.CharField(_("字段名"), max_length=200)
    value = models.TextField(_("字段值"), blank=True, default="")
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 请求字段规格")
        verbose_name_plural = _("API 请求字段规格")
        ordering = ["field_kind", "order", "id"]
        db_table = "api_automation_request_field_spec"

    def __str__(self) -> str:
        return f"{self.request_spec.request.name} - {self.field_kind}:{self.name}"


class ApiRequestFileSpec(models.Model):
    SOURCE_TYPE_CHOICES = [
        ("path", "path"),
        ("base64", "base64"),
        ("placeholder", "placeholder"),
    ]

    request_spec = models.ForeignKey(
        ApiRequestSpec,
        on_delete=models.CASCADE,
        related_name="file_specs",
        verbose_name=_("所属请求规格"),
    )
    field_name = models.CharField(_("表单字段名"), max_length=200)
    source_type = models.CharField(_("文件来源"), max_length=20, choices=SOURCE_TYPE_CHOICES, default="path")
    file_path = models.CharField(_("文件路径"), max_length=500, blank=True, default="")
    file_name = models.CharField(_("文件名"), max_length=255, blank=True, default="")
    content_type = models.CharField(_("文件 Content-Type"), max_length=120, blank=True, default="")
    base64_content = models.TextField(_("文件 Base64 内容"), blank=True, default="")
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 请求文件规格")
        verbose_name_plural = _("API 请求文件规格")
        ordering = ["order", "id"]
        db_table = "api_automation_request_file_spec"

    def __str__(self) -> str:
        return f"{self.request_spec.request.name} - file:{self.field_name}"


class ApiRequestAuthSpec(models.Model):
    AUTH_TYPE_CHOICES = [
        ("none", "none"),
        ("basic", "basic"),
        ("bearer", "bearer"),
        ("api_key", "api_key"),
        ("cookie", "cookie"),
        ("bootstrap_request", "bootstrap_request"),
    ]
    API_KEY_IN_CHOICES = [
        ("header", "header"),
        ("query", "query"),
        ("cookie", "cookie"),
    ]

    request_spec = models.OneToOneField(
        ApiRequestSpec,
        on_delete=models.CASCADE,
        related_name="auth_spec",
        verbose_name=_("认证规格"),
    )
    auth_type = models.CharField(_("认证类型"), max_length=30, choices=AUTH_TYPE_CHOICES, default="none")
    username = models.CharField(_("用户名"), max_length=255, blank=True, default="")
    password = models.CharField(_("密码"), max_length=255, blank=True, default="")
    token_value = models.TextField(_("Token 值"), blank=True, default="")
    token_variable = models.CharField(_("Token 变量名"), max_length=120, blank=True, default="token")
    header_name = models.CharField(_("Header 名"), max_length=120, blank=True, default="Authorization")
    bearer_prefix = models.CharField(_("Bearer 前缀"), max_length=40, blank=True, default="Bearer")
    api_key_name = models.CharField(_("API Key 名"), max_length=120, blank=True, default="")
    api_key_in = models.CharField(_("API Key 位置"), max_length=20, choices=API_KEY_IN_CHOICES, default="header")
    api_key_value = models.TextField(_("API Key 值"), blank=True, default="")
    cookie_name = models.CharField(_("Cookie 名"), max_length=120, blank=True, default="")
    bootstrap_request_id = models.IntegerField(_("引导请求 ID"), null=True, blank=True)
    bootstrap_request_name = models.CharField(_("引导请求名称"), max_length=160, blank=True, default="")
    bootstrap_token_path = models.CharField(_("引导 Token Path"), max_length=255, blank=True, default="")
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 请求认证规格")
        verbose_name_plural = _("API 请求认证规格")
        db_table = "api_automation_request_auth_spec"

    def __str__(self) -> str:
        return f"{self.request_spec.request.name} - auth"


class ApiRequestTransportSpec(models.Model):
    request_spec = models.OneToOneField(
        ApiRequestSpec,
        on_delete=models.CASCADE,
        related_name="transport_spec",
        verbose_name=_("传输规格"),
    )
    verify_ssl = models.BooleanField(_("校验证书"), default=True)
    proxy_url = models.CharField(_("代理地址"), max_length=500, blank=True, default="")
    client_cert = models.CharField(_("客户端证书"), max_length=500, blank=True, default="")
    client_key = models.CharField(_("客户端私钥"), max_length=500, blank=True, default="")
    follow_redirects = models.BooleanField(_("跟随重定向"), default=True)
    retry_count = models.PositiveIntegerField(_("重试次数"), default=0)
    retry_interval_ms = models.PositiveIntegerField(_("重试间隔(ms)"), default=500)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 请求传输规格")
        verbose_name_plural = _("API 请求传输规格")
        db_table = "api_automation_request_transport_spec"

    def __str__(self) -> str:
        return f"{self.request_spec.request.name} - transport"


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


class ApiEnvironmentVariableSpec(models.Model):
    environment = models.ForeignKey(
        ApiEnvironment,
        on_delete=models.CASCADE,
        related_name="variable_specs",
        verbose_name=_("所属环境"),
    )
    name = models.CharField(_("变量名"), max_length=160)
    value = models.TextField(_("变量值"), blank=True, default="")
    enabled = models.BooleanField(_("是否启用"), default=True)
    is_secret = models.BooleanField(_("是否敏感"), default=False)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 环境变量规格")
        verbose_name_plural = _("API 环境变量规格")
        ordering = ["order", "id"]
        unique_together = ("environment", "name")
        db_table = "api_automation_environment_variable_spec"

    def __str__(self) -> str:
        return f"{self.environment.name} - {self.name}"


class ApiEnvironmentHeaderSpec(models.Model):
    environment = models.ForeignKey(
        ApiEnvironment,
        on_delete=models.CASCADE,
        related_name="header_specs",
        verbose_name=_("所属环境"),
    )
    name = models.CharField(_("Header 名"), max_length=160)
    value = models.TextField(_("Header 值"), blank=True, default="")
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 环境 Header 规格")
        verbose_name_plural = _("API 环境 Header 规格")
        ordering = ["order", "id"]
        unique_together = ("environment", "name")
        db_table = "api_automation_environment_header_spec"

    def __str__(self) -> str:
        return f"{self.environment.name} - {self.name}"


class ApiEnvironmentCookieSpec(models.Model):
    environment = models.ForeignKey(
        ApiEnvironment,
        on_delete=models.CASCADE,
        related_name="cookie_specs",
        verbose_name=_("所属环境"),
    )
    name = models.CharField(_("Cookie 名"), max_length=160)
    value = models.TextField(_("Cookie 值"), blank=True, default="")
    domain = models.CharField(_("Domain"), max_length=255, blank=True, default="")
    path = models.CharField(_("Path"), max_length=255, blank=True, default="/")
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 环境 Cookie 规格")
        verbose_name_plural = _("API 环境 Cookie 规格")
        ordering = ["order", "id"]
        unique_together = ("environment", "name", "domain", "path")
        db_table = "api_automation_environment_cookie_spec"

    def __str__(self) -> str:
        return f"{self.environment.name} - {self.name}"


class ApiExecutionRecord(models.Model):
    STATUS_CHOICES = [
        ("success", "success"),
        ("failed", "failed"),
        ("error", "error"),
    ]

    run_id = models.CharField(_("执行批次 ID"), max_length=64, blank=True, default="", db_index=True)
    run_name = models.CharField(_("执行批次名称"), max_length=160, blank=True, default="")

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
    test_case = models.ForeignKey(
        "ApiTestCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_records",
        verbose_name=_("关联测试用例"),
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


class ApiImportJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("running", "running"),
        ("success", "success"),
        ("failed", "failed"),
        ("canceled", "canceled"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_import_jobs",
        verbose_name=_("所属项目"),
    )
    collection = models.ForeignKey(
        ApiCollection,
        on_delete=models.CASCADE,
        related_name="import_jobs",
        verbose_name=_("目标集合"),
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_import_jobs",
        verbose_name=_("创建人"),
    )
    source_name = models.CharField(_("源文档名称"), max_length=255)
    source_file = models.FileField(
        _("源文档文件"),
        upload_to=api_import_job_source_upload_path,
        blank=True,
        null=True,
    )
    status = models.CharField(_("任务状态"), max_length=20, choices=STATUS_CHOICES, default="pending")
    progress_percent = models.PositiveIntegerField(_("进度百分比"), default=0)
    progress_stage = models.CharField(_("当前阶段"), max_length=50, blank=True, default="")
    progress_message = models.TextField(_("阶段说明"), blank=True, default="")
    cancel_requested = models.BooleanField(_("是否请求停止"), default=False)
    generate_test_cases = models.BooleanField(_("是否生成测试用例"), default=True)
    enable_ai_parse = models.BooleanField(_("是否启用AI增强解析"), default=True)
    result_payload = models.JSONField(_("结果载荷"), default=dict, blank=True)
    error_message = models.TextField(_("错误信息"), blank=True, default="")
    completed_at = models.DateTimeField(_("完成时间"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 导入任务")
        verbose_name_plural = _("API 导入任务")
        ordering = ["-created_at"]
        db_table = "api_automation_import_job"

    def __str__(self) -> str:
        return f"{self.source_name} - {self.status}"


class ApiCaseGenerationJob(models.Model):
    SCOPE_CHOICES = [
        ("selected", "selected"),
        ("collection", "collection"),
        ("project", "project"),
    ]

    MODE_CHOICES = [
        ("generate", "generate"),
        ("append", "append"),
        ("regenerate", "regenerate"),
    ]

    STATUS_CHOICES = [
        ("pending", "pending"),
        ("running", "running"),
        ("preview_ready", "preview_ready"),
        ("applying", "applying"),
        ("success", "success"),
        ("failed", "failed"),
        ("canceled", "canceled"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="api_case_generation_jobs",
        verbose_name=_("所属项目"),
    )
    collection = models.ForeignKey(
        ApiCollection,
        on_delete=models.SET_NULL,
        related_name="case_generation_jobs",
        null=True,
        blank=True,
        verbose_name=_("目标集合"),
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_case_generation_jobs",
        verbose_name=_("创建人"),
    )
    scope = models.CharField(_("生成范围"), max_length=20, choices=SCOPE_CHOICES, default="selected")
    mode = models.CharField(_("生成模式"), max_length=20, choices=MODE_CHOICES, default="generate")
    status = models.CharField(_("任务状态"), max_length=20, choices=STATUS_CHOICES, default="pending")
    count_per_request = models.PositiveIntegerField(_("每个接口生成数量"), default=3)
    request_ids = models.JSONField(_("目标接口 ID 列表"), default=list, blank=True)
    progress_percent = models.PositiveIntegerField(_("进度百分比"), default=0)
    progress_stage = models.CharField(_("当前阶段"), max_length=50, blank=True, default="")
    progress_message = models.TextField(_("阶段说明"), blank=True, default="")
    cancel_requested = models.BooleanField(_("是否请求停止"), default=False)
    result_payload = models.JSONField(_("结果载荷"), default=dict, blank=True)
    draft_payload = models.JSONField(_("预览草稿"), default=dict, blank=True)
    error_message = models.TextField(_("错误信息"), blank=True, default="")
    completed_at = models.DateTimeField(_("完成时间"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 用例生成任务")
        verbose_name_plural = _("API 用例生成任务")
        ordering = ["-created_at"]
        db_table = "api_automation_case_generation_job"

    def __str__(self) -> str:
        return f"{self.project.name} - {self.mode} - {self.status}"


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


class ApiTestCaseOverrideSpec(models.Model):
    BODY_MODE_CHOICES = ApiRequestSpec.BODY_MODE_CHOICES

    test_case = models.OneToOneField(
        ApiTestCase,
        on_delete=models.CASCADE,
        related_name="override_spec",
        verbose_name=_("所属测试用例"),
    )
    method = models.CharField(_("覆盖请求方法"), max_length=10, blank=True, default="")
    url = models.TextField(_("覆盖请求地址"), blank=True, default="")
    body_mode = models.CharField(_("覆盖请求体模式"), max_length=20, choices=BODY_MODE_CHOICES, blank=True, default="")
    body_json = models.JSONField(_("覆盖 JSON 请求体"), default=dict, blank=True)
    raw_text = models.TextField(_("覆盖原始文本"), blank=True, default="")
    xml_text = models.TextField(_("覆盖 XML 请求体"), blank=True, default="")
    binary_base64 = models.TextField(_("覆盖二进制 Base64"), blank=True, default="")
    graphql_query = models.TextField(_("覆盖 GraphQL Query"), blank=True, default="")
    graphql_operation_name = models.CharField(_("覆盖 GraphQL Operation"), max_length=120, blank=True, default="")
    graphql_variables = models.JSONField(_("覆盖 GraphQL Variables"), default=dict, blank=True)
    timeout_ms = models.PositiveIntegerField(_("覆盖超时时间(ms)"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 测试用例覆盖规格")
        verbose_name_plural = _("API 测试用例覆盖规格")
        db_table = "api_automation_test_case_override_spec"

    def __str__(self) -> str:
        return f"{self.test_case.name} - override"


class ApiTestCaseFieldSpec(models.Model):
    FIELD_KIND_CHOICES = ApiRequestFieldSpec.FIELD_KIND_CHOICES

    override_spec = models.ForeignKey(
        ApiTestCaseOverrideSpec,
        on_delete=models.CASCADE,
        related_name="field_specs",
        verbose_name=_("所属用例覆盖规格"),
    )
    field_kind = models.CharField(_("字段类型"), max_length=30, choices=FIELD_KIND_CHOICES)
    name = models.CharField(_("字段名"), max_length=200)
    value = models.TextField(_("字段值"), blank=True, default="")
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 测试用例字段规格")
        verbose_name_plural = _("API 测试用例字段规格")
        ordering = ["field_kind", "order", "id"]
        db_table = "api_automation_test_case_field_spec"

    def __str__(self) -> str:
        return f"{self.override_spec.test_case.name} - {self.field_kind}:{self.name}"


class ApiTestCaseFileSpec(models.Model):
    SOURCE_TYPE_CHOICES = ApiRequestFileSpec.SOURCE_TYPE_CHOICES

    override_spec = models.ForeignKey(
        ApiTestCaseOverrideSpec,
        on_delete=models.CASCADE,
        related_name="file_specs",
        verbose_name=_("所属用例覆盖规格"),
    )
    field_name = models.CharField(_("表单字段名"), max_length=200)
    source_type = models.CharField(_("文件来源"), max_length=20, choices=SOURCE_TYPE_CHOICES, default="path")
    file_path = models.CharField(_("文件路径"), max_length=500, blank=True, default="")
    file_name = models.CharField(_("文件名"), max_length=255, blank=True, default="")
    content_type = models.CharField(_("文件 Content-Type"), max_length=120, blank=True, default="")
    base64_content = models.TextField(_("文件 Base64 内容"), blank=True, default="")
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 测试用例文件规格")
        verbose_name_plural = _("API 测试用例文件规格")
        ordering = ["order", "id"]
        db_table = "api_automation_test_case_file_spec"

    def __str__(self) -> str:
        return f"{self.override_spec.test_case.name} - file:{self.field_name}"


class ApiTestCaseAuthSpec(models.Model):
    AUTH_TYPE_CHOICES = ApiRequestAuthSpec.AUTH_TYPE_CHOICES
    API_KEY_IN_CHOICES = ApiRequestAuthSpec.API_KEY_IN_CHOICES

    override_spec = models.OneToOneField(
        ApiTestCaseOverrideSpec,
        on_delete=models.CASCADE,
        related_name="auth_spec",
        verbose_name=_("所属用例覆盖规格"),
    )
    auth_type = models.CharField(_("认证类型"), max_length=30, choices=AUTH_TYPE_CHOICES, blank=True, default="")
    username = models.CharField(_("用户名"), max_length=255, blank=True, default="")
    password = models.CharField(_("密码"), max_length=255, blank=True, default="")
    token_value = models.TextField(_("Token 值"), blank=True, default="")
    token_variable = models.CharField(_("Token 变量名"), max_length=120, blank=True, default="")
    header_name = models.CharField(_("Header 名"), max_length=120, blank=True, default="")
    bearer_prefix = models.CharField(_("Bearer 前缀"), max_length=40, blank=True, default="")
    api_key_name = models.CharField(_("API Key 名"), max_length=120, blank=True, default="")
    api_key_in = models.CharField(_("API Key 位置"), max_length=20, choices=API_KEY_IN_CHOICES, default="header")
    api_key_value = models.TextField(_("API Key 值"), blank=True, default="")
    cookie_name = models.CharField(_("Cookie 名"), max_length=120, blank=True, default="")
    bootstrap_request_id = models.IntegerField(_("引导请求 ID"), null=True, blank=True)
    bootstrap_request_name = models.CharField(_("引导请求名称"), max_length=160, blank=True, default="")
    bootstrap_token_path = models.CharField(_("引导 Token Path"), max_length=255, blank=True, default="")
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 测试用例认证规格")
        verbose_name_plural = _("API 测试用例认证规格")
        db_table = "api_automation_test_case_auth_spec"

    def __str__(self) -> str:
        return f"{self.override_spec.test_case.name} - auth"


class ApiTestCaseTransportSpec(models.Model):
    override_spec = models.OneToOneField(
        ApiTestCaseOverrideSpec,
        on_delete=models.CASCADE,
        related_name="transport_spec",
        verbose_name=_("所属用例覆盖规格"),
    )
    verify_ssl = models.BooleanField(_("校验证书"), null=True, blank=True)
    proxy_url = models.CharField(_("代理地址"), max_length=500, blank=True, default="")
    client_cert = models.CharField(_("客户端证书"), max_length=500, blank=True, default="")
    client_key = models.CharField(_("客户端私钥"), max_length=500, blank=True, default="")
    follow_redirects = models.BooleanField(_("跟随重定向"), null=True, blank=True)
    retry_count = models.PositiveIntegerField(_("重试次数"), null=True, blank=True)
    retry_interval_ms = models.PositiveIntegerField(_("重试间隔(ms)"), null=True, blank=True)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 测试用例传输规格")
        verbose_name_plural = _("API 测试用例传输规格")
        db_table = "api_automation_test_case_transport_spec"

    def __str__(self) -> str:
        return f"{self.override_spec.test_case.name} - transport"


class ApiAssertionSpec(models.Model):
    ASSERTION_TYPE_CHOICES = [
        ("status_code", "status_code"),
        ("status_range", "status_range"),
        ("body_contains", "body_contains"),
        ("body_not_contains", "body_not_contains"),
        ("json_path", "json_path"),
        ("header", "header"),
        ("cookie", "cookie"),
        ("regex", "regex"),
        ("exists", "exists"),
        ("not_exists", "not_exists"),
        ("array_length", "array_length"),
        ("response_time", "response_time"),
        ("json_schema", "json_schema"),
        ("openapi_contract", "openapi_contract"),
    ]

    request = models.ForeignKey(
        ApiRequest,
        on_delete=models.CASCADE,
        related_name="assertion_specs",
        null=True,
        blank=True,
        verbose_name=_("所属请求"),
    )
    test_case = models.ForeignKey(
        ApiTestCase,
        on_delete=models.CASCADE,
        related_name="assertion_specs",
        null=True,
        blank=True,
        verbose_name=_("所属测试用例"),
    )
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    assertion_type = models.CharField(_("断言类型"), max_length=40, choices=ASSERTION_TYPE_CHOICES)
    target = models.CharField(_("断言目标"), max_length=40, blank=True, default="body")
    selector = models.CharField(_("选择器"), max_length=500, blank=True, default="")
    operator = models.CharField(_("运算符"), max_length=40, blank=True, default="equals")
    expected_text = models.TextField(_("期望文本"), blank=True, default="")
    expected_number = models.FloatField(_("期望数值"), null=True, blank=True)
    expected_json = models.JSONField(_("期望 JSON"), default=dict, blank=True)
    min_value = models.FloatField(_("最小值"), null=True, blank=True)
    max_value = models.FloatField(_("最大值"), null=True, blank=True)
    schema_text = models.TextField(_("Schema 文本"), blank=True, default="")
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 断言规格")
        verbose_name_plural = _("API 断言规格")
        ordering = ["order", "id"]
        db_table = "api_automation_assertion_spec"

    def __str__(self) -> str:
        owner = self.test_case.name if self.test_case_id and self.test_case else self.request.name if self.request_id and self.request else "unknown"
        return f"{owner} - {self.assertion_type}"


class ApiExtractorSpec(models.Model):
    SOURCE_TYPE_CHOICES = [
        ("json_path", "json_path"),
        ("header", "header"),
        ("cookie", "cookie"),
        ("regex", "regex"),
        ("status_code", "status_code"),
        ("response_time", "response_time"),
    ]

    request = models.ForeignKey(
        ApiRequest,
        on_delete=models.CASCADE,
        related_name="extractor_specs",
        null=True,
        blank=True,
        verbose_name=_("所属请求"),
    )
    test_case = models.ForeignKey(
        ApiTestCase,
        on_delete=models.CASCADE,
        related_name="extractor_specs",
        null=True,
        blank=True,
        verbose_name=_("所属测试用例"),
    )
    enabled = models.BooleanField(_("是否启用"), default=True)
    order = models.PositiveIntegerField(_("排序"), default=0)
    source = models.CharField(_("提取来源"), max_length=40, choices=SOURCE_TYPE_CHOICES)
    selector = models.CharField(_("选择器"), max_length=500, blank=True, default="")
    variable_name = models.CharField(_("变量名"), max_length=160)
    default_value = models.TextField(_("默认值"), blank=True, default="")
    required = models.BooleanField(_("是否必填"), default=False)
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        verbose_name = _("API 提取器规格")
        verbose_name_plural = _("API 提取器规格")
        ordering = ["order", "id"]
        db_table = "api_automation_extractor_spec"

    def __str__(self) -> str:
        owner = self.test_case.name if self.test_case_id and self.test_case else self.request.name if self.request_id and self.request else "unknown"
        return f"{owner} - {self.variable_name}"
