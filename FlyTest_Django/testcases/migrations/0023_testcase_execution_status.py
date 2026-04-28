from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testcases", "0022_testsuite_hierarchy"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcase",
            name="execution_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("not_executed", "Not Executed"),
                    ("passed", "Passed"),
                    ("failed", "Failed"),
                    ("not_applicable", "Not Applicable"),
                ],
                default="not_executed",
                max_length=20,
                verbose_name="Execution Status",
            ),
        ),
    ]
