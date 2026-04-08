from django.db import models


class _BaseAppAutomationPermissionModel(models.Model):
    class Meta:
        abstract = True
        managed = False
        default_permissions = ("view",)


class AppAutomationOverview(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "APP自动化概览"
        verbose_name_plural = verbose_name


class AppAutomationDevice(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "设备管理"
        verbose_name_plural = verbose_name


class AppAutomationPackage(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "应用包"
        verbose_name_plural = verbose_name


class AppAutomationElement(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "元素管理"
        verbose_name_plural = verbose_name


class AppAutomationSceneBuilder(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "场景编排"
        verbose_name_plural = verbose_name


class AppAutomationTestCase(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "测试用例"
        verbose_name_plural = verbose_name


class AppAutomationSuite(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "测试套件"
        verbose_name_plural = verbose_name


class AppAutomationExecution(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "执行记录"
        verbose_name_plural = verbose_name


class AppAutomationScheduledTask(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "定时任务"
        verbose_name_plural = verbose_name


class AppAutomationNotification(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "通知日志"
        verbose_name_plural = verbose_name


class AppAutomationReport(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "执行报告"
        verbose_name_plural = verbose_name


class AppAutomationSettings(_BaseAppAutomationPermissionModel):
    class Meta(_BaseAppAutomationPermissionModel.Meta):
        verbose_name = "环境设置"
        verbose_name_plural = verbose_name

