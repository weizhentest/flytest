from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0007_alter_project_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="通知标题")),
                ("content", models.TextField(verbose_name="通知内容")),
                (
                    "scope",
                    models.CharField(
                        choices=[("all", "通知所有人"), ("project_members", "通知项目内成员"), ("users", "指定用户通知")],
                        max_length=32,
                        verbose_name="通知范围",
                    ),
                ),
                ("recipient_count", models.PositiveIntegerField(default=0, verbose_name="接收人数")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="site_notifications",
                        to="projects.project",
                        verbose_name="关联项目",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_site_notifications",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="发送人",
                    ),
                ),
            ],
            options={
                "verbose_name": "站内通知",
                "verbose_name_plural": "站内通知",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="SiteNotificationRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_read", models.BooleanField(default=False, verbose_name="是否已读")),
                ("read_at", models.DateTimeField(blank=True, null=True, verbose_name="已读时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "notification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recipients",
                        to="site_notifications.sitenotification",
                        verbose_name="通知",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_notification_receipts",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="接收人",
                    ),
                ),
            ],
            options={
                "verbose_name": "站内通知接收记录",
                "verbose_name_plural": "站内通知接收记录",
                "ordering": ["is_read", "-notification__created_at", "-id"],
                "unique_together": {("notification", "user")},
            },
        ),
    ]
