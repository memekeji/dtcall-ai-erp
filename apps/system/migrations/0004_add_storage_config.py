from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('system', '0003_add_asset_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='StorageProvider',
            fields=[
                ('LOCAL', 'local'),
                ('ALIYUN', 'aliyun'),
                ('TENCENT', 'tencent'),
                ('HUAWEI', 'huawei'),
                ('BAIDU', 'baidu'),
                ('QINIU', 'qiniu'),
                ('AWS', 'aws'),
                ('FEINIU_NAS', 'feiniu_nas'),
                ('QUNHUI_NAS', 'qunhui_nas'),
                ('WEBDAV', 'webdav'),
            ],
        ),
        migrations.CreateModel(
            name='StorageConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='配置名称')),
                ('storage_type', models.CharField(max_length=50, verbose_name='存储类型')),
                ('is_default', models.BooleanField(default=False, verbose_name='是否默认')),
                ('access_key', models.CharField(blank=True, max_length=200, verbose_name='AccessKey')),
                ('secret_key', models.CharField(blank=True, max_length=200, verbose_name='SecretKey')),
                ('bucket_name', models.CharField(blank=True, max_length=100, verbose_name='存储桶名称')),
                ('endpoint', models.CharField(blank=True, max_length=200, verbose_name='Endpoint地址')),
                ('region', models.CharField(blank=True, max_length=100, verbose_name='区域')),
                ('domain', models.CharField(blank=True, max_length=200, verbose_name='访问域名')),
                ('base_path', models.CharField(blank=True, max_length=200, verbose_name='基础路径')),
                ('nas_host', models.CharField(blank=True, max_length=200, verbose_name='NAS主机地址')),
                ('nas_port', models.IntegerField(default=0, verbose_name='NAS端口')),
                ('nas_share_path', models.CharField(blank=True, max_length=200, verbose_name='共享路径')),
                ('webdav_url', models.CharField(blank=True, max_length=500, verbose_name='WebDAV地址')),
                ('webdav_username', models.CharField(blank=True, max_length=100, verbose_name='WebDAV用户名')),
                ('webdav_password', models.CharField(blank=True, max_length=100, verbose_name='WebDAV密码')),
                ('local_path', models.CharField(blank=True, max_length=500, verbose_name='本地存储路径')),
                ('max_file_size', models.BigIntegerField(default=0, verbose_name='最大文件大小(字节)')),
                ('allowed_extensions', models.TextField(blank=True, verbose_name='允许的文件扩展名')),
                ('status', models.CharField(choices=[('active', '启用'), ('inactive', '禁用'), ('testing', '测试中'), ('error', '错误')], default='inactive', max_length=20, verbose_name='状态')),
                ('last_test_time', models.DateTimeField(blank=True, null=True, verbose_name='最后测试时间')),
                ('last_error', models.TextField(blank=True, verbose_name='最后错误信息')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('creator', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '存储配置',
                'verbose_name_plural': '存储配置',
                'db_table': 'system_storage_config',
                'ordering': ['-is_default', 'name'],
            },
        ),
    ]
