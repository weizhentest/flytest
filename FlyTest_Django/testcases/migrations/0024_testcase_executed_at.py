from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testcases", "0023_testcase_execution_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcase",
            name="executed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Execution Time"),
        ),
    ]
