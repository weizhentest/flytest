from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("testcases", "0030_testbug_related_testcases_alter_testbug_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="TestBugActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("create", "新建"),
                            ("update", "编辑"),
                            ("assign", "指派"),
                            ("confirm", "确认"),
                            ("fix", "修复"),
                            ("resolve", "提交复测"),
                            ("activate", "激活"),
                            ("close", "关闭"),
                            ("status_change", "状态变更"),
                            ("upload_attachment", "上传附件"),
                            ("delete_attachment", "删除附件"),
                        ],
                        max_length=40,
                        verbose_name="操作类型",
                    ),
                ),
                ("content", models.TextField(blank=True, default="", verbose_name="操作内容")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="附加数据")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="操作时间")),
                (
                    "bug",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="testcases.testbug",
                        verbose_name="所属Bug",
                    ),
                ),
                (
                    "operator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="operated_test_bug_activities",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="操作人",
                    ),
                ),
            ],
            options={
                "verbose_name": "测试Bug操作历史",
                "verbose_name_plural": "测试Bug操作历史",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
