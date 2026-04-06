from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from projects.models import Project


class DataFactoryTag(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="data_factory_tags",
        verbose_name=_("所属项目"),
    )
    name = models.CharField(_("标签名称"), max_length=80)
    code = models.CharField(_("引用编码"), max_length=120)
    description = models.TextField(_("标签说明"), blank=True, default="")
    color = models.CharField(_("标签颜色"), max_length=32, blank=True, default="")
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_data_factory_tags",
        verbose_name=_("创建人"),
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        db_table = "data_factory_tag"
        verbose_name = _("数据工厂标签")
        verbose_name_plural = _("数据工厂标签")
        ordering = ["project_id", "name", "id"]
        unique_together = ("project", "name"), ("project", "code")
        indexes = [
            models.Index(fields=["project", "name"]),
            models.Index(fields=["project", "code"]),
        ]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.name}"


class DataFactoryRecord(models.Model):
    TOOL_CATEGORY_CHOICES = [
        ("string", _("字符工具")),
        ("encoding", _("编码工具")),
        ("random", _("随机工具")),
        ("encryption", _("加密工具")),
        ("test_data", _("测试数据")),
        ("json", _("JSON 工具")),
        ("crontab", _("Crontab 工具")),
    ]
    TOOL_SCENARIO_CHOICES = [
        ("data_generation", _("数据生成")),
        ("format_conversion", _("格式转换")),
        ("data_validation", _("数据验证")),
        ("encryption_decryption", _("加密解密")),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="data_factory_records",
        verbose_name=_("所属项目"),
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_data_factory_records",
        verbose_name=_("创建人"),
    )
    tool_name = models.CharField(_("工具编码"), max_length=100)
    tool_category = models.CharField(_("工具分类"), max_length=32, choices=TOOL_CATEGORY_CHOICES)
    tool_scenario = models.CharField(_("使用场景"), max_length=32, choices=TOOL_SCENARIO_CHOICES)
    input_data = models.JSONField(_("输入数据"), default=dict, blank=True)
    output_data = models.JSONField(_("输出数据"), default=dict, blank=True)
    is_saved = models.BooleanField(_("是否保存"), default=True)
    tags = models.ManyToManyField(
        DataFactoryTag,
        related_name="records",
        verbose_name=_("标签"),
        blank=True,
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新时间"), auto_now=True)

    class Meta:
        db_table = "data_factory_record"
        verbose_name = _("数据工厂记录")
        verbose_name_plural = _("数据工厂记录")
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["project", "-created_at"]),
            models.Index(fields=["creator", "-created_at"]),
            models.Index(fields=["project", "tool_category"]),
            models.Index(fields=["project", "tool_scenario"]),
            models.Index(fields=["project", "is_saved"]),
        ]

    def __str__(self) -> str:
        return f"{self.project_id}:{self.tool_name}:{self.pk}"

# Create your models here.
