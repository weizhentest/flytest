from django.conf import settings
from django.db import migrations, models


def migrate_testbug_statuses(apps, schema_editor):
    TestBug = apps.get_model("testcases", "TestBug")

    for bug in TestBug.objects.all().iterator():
        if bug.status == "active":
            bug.status = "assigned" if bug.assigned_to_id else "unassigned"
        elif bug.status == "resolved":
            bug.status = "pending_retest"
        elif bug.status == "closed":
            bug.status = "closed"
        elif bug.status not in {
            "unassigned",
            "assigned",
            "confirmed",
            "fixed",
            "pending_retest",
            "closed",
            "expired",
        }:
            bug.status = "assigned" if bug.assigned_to_id else "unassigned"
        bug.save(update_fields=["status"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("testcases", "0026_testbugattachment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="testbug",
            name="status",
            field=models.CharField(
                choices=[
                    ("unassigned", "未指派"),
                    ("assigned", "已指派"),
                    ("confirmed", "已确认"),
                    ("fixed", "已修复"),
                    ("pending_retest", "待复测"),
                    ("closed", "已关闭"),
                    ("expired", "已过期"),
                ],
                default="unassigned",
                max_length=20,
                verbose_name="状态",
            ),
        ),
        migrations.RunPython(migrate_testbug_statuses, migrations.RunPython.noop),
    ]
