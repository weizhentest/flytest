from django.db import migrations, models

import testcase_templates.models


class Migration(migrations.Migration):

    dependencies = [
        ('testcase_templates', '0002_importexporttemplate_template_headers'),
    ]

    operations = [
        migrations.AddField(
            model_name='importexporttemplate',
            name='template_file',
            field=models.FileField(blank=True, help_text='用户上传的Excel模板文件（用于导出保持样式、合并单元格、标题等）', null=True, upload_to=testcase_templates.models.testcase_template_upload_path, verbose_name='模板文件'),
        ),
    ]

