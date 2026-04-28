from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
        ("testcases", "0024_testcase_executed_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TestBug",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="Bug标题")),
                ("steps", models.TextField(blank=True, default="", verbose_name="重现步骤")),
                ("expected_result", models.TextField(blank=True, default="", verbose_name="期望结果")),
                ("actual_result", models.TextField(blank=True, default="", verbose_name="实际结果")),
                ("bug_type", models.CharField(choices=[("codeerror", "Code Error"), ("config", "Config"), ("install", "Install"), ("security", "Security"), ("performance", "Performance"), ("standard", "Standard"), ("design", "Design"), ("others", "Others")], default="codeerror", max_length=20, verbose_name="Bug类型")),
                ("severity", models.CharField(choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")], default="3", max_length=1, verbose_name="严重程度")),
                ("priority", models.CharField(choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")], default="3", max_length=1, verbose_name="优先级")),
                ("status", models.CharField(choices=[("active", "Active"), ("resolved", "Resolved"), ("closed", "Closed")], default="active", max_length=20, verbose_name="状态")),
                ("resolution", models.CharField(blank=True, choices=[("", "-"), ("fixed", "Fixed"), ("postponed", "Postponed"), ("notrepro", "Not Repro"), ("external", "External"), ("duplicate", "Duplicate"), ("wontfix", "Wont Fix"), ("bydesign", "By Design")], default="", max_length=20, verbose_name="解决方案")),
                ("keywords", models.CharField(blank=True, default="", max_length=255, verbose_name="关键词")),
                ("deadline", models.DateField(blank=True, null=True, verbose_name="截止日期")),
                ("opened_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("assigned_at", models.DateTimeField(blank=True, null=True, verbose_name="指派时间")),
                ("resolved_at", models.DateTimeField(blank=True, null=True, verbose_name="解决时间")),
                ("closed_at", models.DateTimeField(blank=True, null=True, verbose_name="关闭时间")),
                ("activated_at", models.DateTimeField(blank=True, null=True, verbose_name="激活时间")),
                ("activated_count", models.PositiveIntegerField(default=0, verbose_name="激活次数")),
                ("solution", models.TextField(blank=True, default="", verbose_name="处理备注")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("activated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activated_test_bugs", to=settings.AUTH_USER_MODEL, verbose_name="由谁激活")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_test_bugs", to=settings.AUTH_USER_MODEL, verbose_name="指派给")),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="closed_test_bugs", to=settings.AUTH_USER_MODEL, verbose_name="由谁关闭")),
                ("opened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_test_bugs", to=settings.AUTH_USER_MODEL, verbose_name="由谁创建")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="test_bugs", to="projects.project", verbose_name="所属项目")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_test_bugs", to=settings.AUTH_USER_MODEL, verbose_name="由谁解决")),
                ("suite", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bugs", to="testcases.testsuite", verbose_name="所属套件")),
                ("testcase", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bugs", to="testcases.testcase", verbose_name="关联测试用例")),
            ],
            options={
                "verbose_name": "测试Bug",
                "verbose_name_plural": "测试Bug",
                "ordering": ["-id"],
            },
        ),
    ]
