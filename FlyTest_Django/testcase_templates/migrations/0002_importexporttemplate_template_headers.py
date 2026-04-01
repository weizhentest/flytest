from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testcase_templates', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='importexporttemplate',
            name='template_headers',
            field=models.JSONField(blank=True, default=list, help_text='上传/解析得到的Excel表头列表（含列顺序），用于导出保持表格结构', verbose_name='模板表头结构'),
        ),
    ]

