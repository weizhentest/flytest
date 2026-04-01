from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api_automation", "0004_apiimportjob_cancel_requested_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiexecutionrecord",
            name="run_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="执行批次 ID"),
        ),
        migrations.AddField(
            model_name="apiexecutionrecord",
            name="run_name",
            field=models.CharField(blank=True, default="", max_length=160, verbose_name="执行批次名称"),
        ),
        migrations.AddField(
            model_name="apiexecutionrecord",
            name="test_case",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="execution_records",
                to="api_automation.apitestcase",
                verbose_name="关联测试用例",
            ),
        ),
    ]
