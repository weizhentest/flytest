from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testcases", "0020_add_test_type_field"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TestCaseAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="created_testcase_assignments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="分配人",
                    ),
                ),
                (
                    "assignee",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="testcase_assignments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="执行人",
                    ),
                ),
                (
                    "suite",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="assigned_testcases",
                        to="testcases.testsuite",
                        verbose_name="测试套件",
                    ),
                ),
                (
                    "testcase",
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        related_name="assignment",
                        to="testcases.testcase",
                        verbose_name="测试用例",
                    ),
                ),
            ],
            options={
                "verbose_name": "测试用例分配",
                "verbose_name_plural": "测试用例分配",
                "ordering": ["-updated_at"],
            },
        ),
    ]
