from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ui_automation", "0005_ai_enable_gif"),
    ]

    operations = [
        migrations.CreateModel(
            name="UiActuator",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ],
            options={
                "verbose_name": "UI 执行器",
                "verbose_name_plural": "UI 执行器",
                "managed": False,
                "default_permissions": ("view",),
            },
        ),
    ]
