from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AppAutomationOverview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "APP自动化概览",
                "verbose_name_plural": "APP自动化概览",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "设备管理",
                "verbose_name_plural": "设备管理",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "应用包",
                "verbose_name_plural": "应用包",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationElement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "元素管理",
                "verbose_name_plural": "元素管理",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationSceneBuilder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "场景编排",
                "verbose_name_plural": "场景编排",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationTestCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "测试用例",
                "verbose_name_plural": "测试用例",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationSuite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "测试套件",
                "verbose_name_plural": "测试套件",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "执行记录",
                "verbose_name_plural": "执行记录",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationScheduledTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "定时任务",
                "verbose_name_plural": "定时任务",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "通知日志",
                "verbose_name_plural": "通知日志",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "执行报告",
                "verbose_name_plural": "执行报告",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
        migrations.CreateModel(
            name="AppAutomationSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "环境设置",
                "verbose_name_plural": "环境设置",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
    ]
