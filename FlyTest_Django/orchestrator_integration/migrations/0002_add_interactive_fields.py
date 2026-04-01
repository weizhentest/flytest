# Generated manually for interactive orchestrator feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orchestrator_integration', '0001_initial'),
    ]

    operations = [
        # 修改 status 字段长度
        migrations.AlterField(
            model_name='orchestratortask',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', '待处理'),
                    ('planning', '规划中'),
                    ('waiting_confirmation', '等待确认'),
                    ('executing', '执行中'),
                    ('completed', '已完成'),
                    ('failed', '失败'),
                    ('cancelled', '已取消')
                ],
                default='pending',
                max_length=30
            ),
        ),
        # 添加交互式执行字段
        migrations.AddField(
            model_name='orchestratortask',
            name='execution_plan',
            field=models.JSONField(blank=True, null=True, verbose_name='执行计划'),
        ),
        migrations.AddField(
            model_name='orchestratortask',
            name='execution_history',
            field=models.JSONField(blank=True, default=list, verbose_name='执行历史'),
        ),
        migrations.AddField(
            model_name='orchestratortask',
            name='current_step',
            field=models.IntegerField(default=0, verbose_name='当前步骤'),
        ),
        migrations.AddField(
            model_name='orchestratortask',
            name='waiting_for',
            field=models.CharField(blank=True, max_length=50, verbose_name='等待对象'),
        ),
        migrations.AddField(
            model_name='orchestratortask',
            name='user_notes',
            field=models.TextField(blank=True, verbose_name='用户备注'),
        ),
        # 修改 execution_log 的 verbose_name
        migrations.AlterField(
            model_name='orchestratortask',
            name='execution_log',
            field=models.JSONField(blank=True, default=list, verbose_name='执行日志(旧)'),
        ),
    ]