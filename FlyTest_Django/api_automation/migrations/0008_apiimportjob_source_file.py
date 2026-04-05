from django.db import migrations, models

import api_automation.models


class Migration(migrations.Migration):

    dependencies = [
        ("api_automation", "0007_apicasegenerationjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiimportjob",
            name="source_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=api_automation.models.api_import_job_source_upload_path,
                verbose_name="源文档文件",
            ),
        ),
    ]
