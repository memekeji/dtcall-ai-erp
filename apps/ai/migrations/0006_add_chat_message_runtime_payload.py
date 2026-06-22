from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0005_workflowwebhook_workflowversion_workflowtemplate_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='aichatmessage',
            name='runtime_payload',
            field=models.JSONField(
                default=dict,
                blank=True,
                verbose_name='运行时结构化数据'),
        ),
    ]
