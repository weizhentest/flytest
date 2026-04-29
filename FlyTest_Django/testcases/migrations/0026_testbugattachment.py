from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import testcases.models


class Migration(migrations.Migration):

    dependencies = [
        ("testcases", "0025_testbug"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TestBugAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("section", models.CharField(choices=[("steps", "重现步骤"), ("expected_result", "期望结果"), ("actual_result", "实际结果")], max_length=30, verbose_name="所属区域")),
                ("attachment", models.FileField(upload_to=testcases.models.testbug_attachment_path, verbose_name="附件")),
                ("original_name", models.CharField(blank=True, default="", max_length=255, verbose_name="原始文件名")),
                ("file_type", models.CharField(choices=[("image", "图片"), ("video", "视频"), ("file", "文件")], default="file", max_length=20, verbose_name="附件类型")),
                ("content_type", models.CharField(blank=True, default="", max_length=120, verbose_name="内容类型")),
                ("file_size", models.PositiveBigIntegerField(default=0, verbose_name="文件大小")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="上传时间")),
                ("bug", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="testcases.testbug", verbose_name="所属Bug")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_test_bug_attachments", to=settings.AUTH_USER_MODEL, verbose_name="上传人")),
            ],
            options={
                "verbose_name": "测试Bug附件",
                "verbose_name_plural": "测试Bug附件",
                "ordering": ["section", "-created_at", "-id"],
            },
        ),
    ]
