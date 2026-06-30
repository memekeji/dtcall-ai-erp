# Generated migration: Simplify AIModelConfig
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0006_add_chat_message_runtime_payload'),
    ]

    operations = [
        # First remove the unique_together constraint
        migrations.AlterUniqueTogether(
            name='aimodelconfig',
            unique_together=set(),
        ),
        # Then remove old fields
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='provider',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='model_type',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='model_name',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='project',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='max_tokens',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='temperature',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='top_p',
        ),
        migrations.RemoveField(
            model_name='aimodelconfig',
            name='is_default',
        ),
        # Modify api_base
        migrations.AlterField(
            model_name='aimodelconfig',
            name='api_base',
            field=models.URLField(
                help_text='OpenAI\u517c\u5bb9\u7684API\u63a5\u53e3\u5730\u5740',
                max_length=300,
                verbose_name='API\u63a5\u53e3\u5730\u5740',
            ),
        ),
        migrations.AlterField(
            model_name='aimodelconfig',
            name='name',
            field=models.CharField(
                default='\u9ed8\u8ba4\u914d\u7f6e',
                max_length=100,
                verbose_name='\u914d\u7f6e\u540d\u79f0',
            ),
        ),
        # Add new fields
        migrations.AddField(
            model_name='aimodelconfig',
            name='image_model',
            field=models.CharField(
                default='gpt-image-1',
                help_text='\u7528\u4e8e\u56fe\u7247\u751f\u6210\u7684\u6a21\u578b\u6807\u8bc6',
                max_length=100,
                verbose_name='\u56fe\u7247\u6a21\u578b\u540d\u79f0',
            ),
        ),
        migrations.AddField(
            model_name='aimodelconfig',
            name='video_model',
            field=models.CharField(
                blank=True,
                default='sora-1',
                help_text='\u7528\u4e8e\u89c6\u9891\u751f\u6210\u7684\u6a21\u578b\u6807\u8bc6',
                max_length=100,
                verbose_name='\u89c6\u9891\u6a21\u578b\u540d\u79f0',
            ),
        ),
    ]
