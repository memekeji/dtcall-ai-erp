from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0002_initial'),
        ('contract', '0007_add_legal_consult_record'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchase',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='purchases',
                to='project.project',
                verbose_name='关联项目',
            ),
        ),
    ]
