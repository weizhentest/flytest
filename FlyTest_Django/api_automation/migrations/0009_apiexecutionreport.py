from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api_automation", "0008_apiimportjob_source_file"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiExecutionReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "API 测试报告",
                "verbose_name_plural": "API 测试报告",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
    ]
