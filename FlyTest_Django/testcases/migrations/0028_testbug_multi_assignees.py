from django.conf import settings
from django.db import migrations, models


def backfill_assigned_users(apps, schema_editor):
    TestBug = apps.get_model("testcases", "TestBug")
    for bug in TestBug.objects.exclude(assigned_to_id__isnull=True).iterator():
        bug.assigned_users.add(bug.assigned_to_id)


def rollback_assigned_users(apps, schema_editor):
    TestBug = apps.get_model("testcases", "TestBug")
    for bug in TestBug.objects.iterator():
        first_user = bug.assigned_users.order_by("id").first()
        bug.assigned_to_id = first_user.id if first_user else None
        bug.save(update_fields=["assigned_to"])


class Migration(migrations.Migration):

    dependencies = [
        ("testcases", "0027_testbug_status_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="testbug",
            name="assigned_users",
            field=models.ManyToManyField(
                blank=True,
                related_name="multi_assigned_test_bugs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="鎸囨淳缁勬垚鍛?",
            ),
        ),
        migrations.RunPython(backfill_assigned_users, rollback_assigned_users),
    ]
