# Generated manually for review progress tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requirements', '0006_add_logic_analysis'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewreport',
            name='progress',
            field=models.IntegerField(default=0, help_text='0-100', verbose_name='评审进度'),
        ),
        migrations.AddField(
            model_name='reviewreport',
            name='current_step',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='当前步骤'),
        ),
        migrations.AddField(
            model_name='reviewreport',
            name='completed_steps',
            field=models.JSONField(blank=True, default=list, verbose_name='已完成步骤'),
        ),
    ]
