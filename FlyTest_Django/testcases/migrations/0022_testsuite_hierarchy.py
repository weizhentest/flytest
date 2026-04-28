from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("testcases", "0021_testcaseassignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="testsuite",
            name="level",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="套件级别"),
        ),
        migrations.AddField(
            model_name="testsuite",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="children",
                to="testcases.testsuite",
                verbose_name="父套件",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="testsuite",
            unique_together={("project", "parent", "name")},
        ),
    ]
