from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "待审核"), ("approved", "已通过"), ("rejected", "已驳回")], default="pending", max_length=20, verbose_name="审核状态")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True, verbose_name="审核时间")),
                ("review_note", models.TextField(blank=True, default="", verbose_name="审核备注")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_user_approvals", to=settings.AUTH_USER_MODEL, verbose_name="审核人")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="approval_record", to=settings.AUTH_USER_MODEL, verbose_name="用户")),
            ],
            options={
                "verbose_name": "用户注册审核",
                "verbose_name_plural": "用户注册审核",
                "ordering": ["-updated_at", "-created_at"],
            },
        ),
    ]
