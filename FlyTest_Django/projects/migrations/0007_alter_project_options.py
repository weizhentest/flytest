from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0006_projectdeletionrequest_project_delete_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['id'], 'verbose_name': '项目', 'verbose_name_plural': '项目'},
        ),
    ]
