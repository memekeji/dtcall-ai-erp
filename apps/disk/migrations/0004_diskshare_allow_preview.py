from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('disk', '0003_diskfile_ai_content_text_diskfile_ai_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='diskshare',
            name='allow_preview',
            field=models.BooleanField(default=True, verbose_name='允许预览'),
        ),
    ]
