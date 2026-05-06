from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("site_notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteNotificationReply",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(verbose_name="回复内容")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "notification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="replies",
                        to="site_notifications.sitenotification",
                        verbose_name="通知",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_notification_replies",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="回复人",
                    ),
                ),
            ],
            options={
                "verbose_name": "站内通知回复",
                "verbose_name_plural": "站内通知回复",
                "ordering": ["created_at", "id"],
            },
        ),
    ]
