from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0005_add_sync_to_local'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='配置名称')),
                ('category', models.CharField(choices=[('sms', '短信服务'), ('stt', '语音转文本'), ('tts', '文本转语音'), ('ocr', 'OCR识别'), ('ai', 'AI智能服务')], max_length=20, verbose_name='服务类别')),
                ('provider', models.CharField(max_length=50, verbose_name='服务商')),
                ('api_key', models.CharField(blank=True, max_length=500, verbose_name='API密钥')),
                ('api_secret', models.CharField(blank=True, max_length=500, verbose_name='API密钥Secret')),
                ('base_url', models.CharField(blank=True, max_length=500, verbose_name='接口地址')),
                ('extra_config', models.TextField(blank=True, verbose_name='额外配置(JSON格式)')),
                ('is_enabled', models.BooleanField(default=False, verbose_name='是否启用')),
                ('status', models.CharField(choices=[('active', '启用'), ('inactive', '禁用'), ('testing', '测试中'), ('error', '错误')], default='inactive', max_length=20, verbose_name='状态')),
                ('last_test_time', models.DateTimeField(blank=True, null=True, verbose_name='最后测试时间')),
                ('last_error', models.TextField(blank=True, verbose_name='最后错误信息')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('creator', models.ForeignKey(null=True, on_delete=models.SET_NULL, to='user.Admin', verbose_name='创建人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '服务配置',
                'verbose_name_plural': '服务配置',
                'db_table': 'system_service_config',
                'ordering': ['category', 'name'],
            },
        ),
    ]
