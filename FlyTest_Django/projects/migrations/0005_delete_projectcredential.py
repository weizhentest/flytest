from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0004_remove_project_password_remove_project_system_url_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ProjectCredential',
        ),
    ]
