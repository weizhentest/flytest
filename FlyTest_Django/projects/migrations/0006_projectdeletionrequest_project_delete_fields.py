from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0005_delete_projectcredential'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='删除时间'),
        ),
        migrations.AddField(
            model_name='project',
            name='deleted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='deleted_projects',
                to=settings.AUTH_USER_MODEL,
                verbose_name='删除人',
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='is_deleted',
            field=models.BooleanField(default=False, verbose_name='是否已删除'),
        ),
        migrations.CreateModel(
            name='ProjectDeletionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_name', models.CharField(max_length=100, verbose_name='项目名称快照')),
                ('project_display_id', models.PositiveIntegerField(verbose_name='项目ID快照')),
                ('requested_by_name', models.CharField(blank=True, default='', max_length=100, verbose_name='申请人姓名')),
                ('request_note', models.TextField(blank=True, default='', verbose_name='申请说明')),
                ('status', models.CharField(
                    choices=[('pending', '待审核'), ('approved', '已删除'), ('rejected', '已驳回'), ('restored', '已恢复')],
                    default='pending',
                    max_length=20,
                    verbose_name='状态',
                )),
                ('reviewed_by_name', models.CharField(blank=True, default='', max_length=100, verbose_name='审核人姓名')),
                ('review_note', models.TextField(blank=True, default='', verbose_name='审核备注')),
                ('requested_at', models.DateTimeField(auto_now_add=True, verbose_name='申请时间')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='审核时间')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('restored_at', models.DateTimeField(blank=True, null=True, verbose_name='恢复时间')),
                ('restored_by_name', models.CharField(blank=True, default='', max_length=100, verbose_name='恢复人姓名')),
                ('project', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='deletion_requests',
                    to='projects.project',
                    verbose_name='项目',
                )),
                ('requested_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='project_deletion_requests',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='申请人',
                )),
                ('restored_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='restored_project_deletion_requests',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='恢复人',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_project_deletion_requests',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='审核人',
                )),
            ],
            options={
                'verbose_name': '项目删除记录',
                'verbose_name_plural': '项目删除记录',
                'ordering': ['-requested_at'],
            },
        ),
    ]
