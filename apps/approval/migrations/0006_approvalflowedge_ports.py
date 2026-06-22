from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approval', '0005_approval_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalflowedge',
            name='source_port',
            field=models.CharField(blank=True, default='output_2', max_length=30, verbose_name='源连接点'),
        ),
        migrations.AddField(
            model_name='approvalflowedge',
            name='target_port',
            field=models.CharField(blank=True, default='input_2', max_length=30, verbose_name='目标连接点'),
        ),
    ]
