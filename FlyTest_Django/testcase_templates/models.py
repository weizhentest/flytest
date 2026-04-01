from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

import os


def testcase_template_upload_path(instance, filename):
    return os.path.join('testcase_templates', filename)


class ImportExportTemplate(models.Model):
    """
    用例 Excel 导入/导出模板（全局级别）
    用户可以上传 Excel 模版，配置字段映射和值转换规则，保存为可复用的导入导出模版
    """
    TEMPLATE_TYPE_CHOICES = [
        ('import', _('导入')),
        ('export', _('导出')),
        ('both', _('导入/导出')),
    ]

    STEP_PARSING_MODE_CHOICES = [
        ('single_cell', _('单元格合并步骤')),  # [1]步骤1\n[2]步骤2
        ('multi_row', _('多行步骤')),          # 每行一个步骤
    ]

    name = models.CharField(_('模板名称'), max_length=255, unique=True)
    template_type = models.CharField(
        _('模板类型'),
        max_length=10,
        choices=TEMPLATE_TYPE_CHOICES,
        default='import'
    )
    description = models.TextField(_('模板描述'), blank=True, null=True)

    # 表头配置
    sheet_name = models.CharField(
        _('工作表名称'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('为空则默认使用第一个工作表')
    )
    template_file = models.FileField(
        _('模板文件'),
        upload_to=testcase_template_upload_path,
        blank=True,
        null=True,
        help_text=_('用户上传的Excel模板文件（用于导出保持样式、合并单元格、标题等）')
    )
    template_headers = models.JSONField(
        _('模板表头结构'),
        default=list,
        blank=True,
        help_text=_('上传/解析得到的Excel表头列表（含列顺序），用于导出保持表格结构')
    )
    header_row = models.PositiveIntegerField(
        _('表头行号'),
        default=1,
        help_text=_('Excel中字段名所在行(从1开始)')
    )
    data_start_row = models.PositiveIntegerField(
        _('数据起始行号'),
        default=2,
        help_text=_('数据从第几行开始(从1开始)，支持表头和数据之间有空行')
    )

    # 字段映射配置 (JSONField)
    # 格式: {"name": "用例名称", "module": "所属模块", "level": "优先级", "precondition": "前置条件", "notes": "备注"}
    field_mappings = models.JSONField(
        _('字段映射'),
        default=dict,
        blank=True,
        help_text=_('内部字段名到Excel列名的映射，如 {"name": "用例名称", "level": "优先级"}')
    )

    # 值转换规则 (JSONField)
    # 格式: {"level": {"高": "P0", "中": "P1", "低": "P2"}}
    value_transformations = models.JSONField(
        _('值转换规则'),
        default=dict,
        blank=True,
        help_text=_('字段值转换规则，如 {"level": {"高": "P0", "中": "P1", "低": "P2"}}')
    )

    # 步骤解析配置
    step_parsing_mode = models.CharField(
        _('步骤解析模式'),
        max_length=20,
        choices=STEP_PARSING_MODE_CHOICES,
        default='single_cell'
    )
    # step_config 示例:
    # single_cell模式: {"step_column": "步骤描述", "expected_column": "预期结果", "pattern": "[{num}]{content}"}
    # multi_row模式: {"step_column": "步骤描述", "expected_column": "预期结果", "case_identifier_column": "用例名称"}
    step_config = models.JSONField(
        _('步骤解析配置'),
        default=dict,
        blank=True,
        help_text=_('步骤解析的详细配置，包括列名和格式模式')
    )

    # 模块路径配置
    module_path_delimiter = models.CharField(
        _('模块路径分隔符'),
        max_length=10,
        default='/',
        help_text=_('Excel中模块路径的分隔符，如 "/" 或 ">"')
    )

    # 元数据
    is_active = models.BooleanField(_('是否启用'), default=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_import_export_templates',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('用例导入导出模板')
        verbose_name_plural = _('用例导入导出模板')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['is_active', 'template_type']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def get_column_for_field(self, field_name: str) -> str | None:
        """根据内部字段名获取对应的Excel列名"""
        return self.field_mappings.get(field_name)

    def transform_value(self, field_name: str, value: str) -> str:
        """应用值转换规则"""
        if field_name in self.value_transformations:
            mapping = self.value_transformations[field_name]
            return mapping.get(value, value)
        return value
