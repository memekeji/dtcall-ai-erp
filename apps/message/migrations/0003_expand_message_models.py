from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('message', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageCategory',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='分类名称')),
                ('code', models.CharField(max_length=30, unique=True, verbose_name='分类代码')),
                ('type', models.CharField(choices=[('announcement', '公告通知'), ('approval', '审批通知'), ('task', '任务通知'), ('system', '系统通知'), ('comment', '评论回复通知')], max_length=20, verbose_name='消息类型')),
                ('icon', models.CharField(default='layui-icon-notice', max_length=50, verbose_name='图标')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='描述')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '消息分类',
                'verbose_name_plural': '消息分类',
                'ordering': ['sort_order', 'id'],
                'db_table': 'message_category',
            },
        ),
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('enable_email', models.BooleanField(default=True, verbose_name='启用邮件通知')),
                ('enable_browser', models.BooleanField(default=True, verbose_name='启用浏览器通知')),
                ('quiet_hours_start', models.TimeField(blank=True, null=True, verbose_name='免打扰开始时间')),
                ('quiet_hours_end', models.TimeField(blank=True, null=True, verbose_name='免打扰结束时间')),
                ('notify_announcement', models.BooleanField(default=True, verbose_name='公告通知')),
                ('notify_approval', models.BooleanField(default=True, verbose_name='审批通知')),
                ('notify_task', models.BooleanField(default=True, verbose_name='任务通知')),
                ('notify_comment', models.BooleanField(default=True, verbose_name='评论通知')),
                ('notify_system', models.BooleanField(default=True, verbose_name='系统通知')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.OneToOneField(on_delete=models.CASCADE, related_name='notification_preference', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户通知偏好',
                'verbose_name_plural': '用户通知偏好',
                'db_table': 'notification_preference',
            },
        ),
        migrations.AddField(
            model_name='message',
            name='category',
            field=models.ForeignKey(null=True, on_delete=models.SET_NULL, to='message.messagecategory', verbose_name='消息分类'),
        ),
        migrations.AddField(
            model_name='message',
            name='content',
            field=models.TextField(default='', verbose_name='消息内容'),
        ),
        migrations.AddField(
            model_name='message',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='创建时间'),
        ),
        migrations.AddField(
            model_name='message',
            name='expire_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='过期时间'),
        ),
        migrations.AddField(
            model_name='message',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='是否有效'),
        ),
        migrations.AddField(
            model_name='message',
            name='is_broadcast',
            field=models.BooleanField(default=False, verbose_name='是否广播消息'),
        ),
        migrations.AddField(
            model_name='message',
            name='priority',
            field=models.IntegerField(choices=[(1, '低'), (2, '普通'), (3, '高'), (4, '紧急')], default=2, verbose_name='优先级'),
        ),
        migrations.AddField(
            model_name='message',
            name='related_object_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='关联对象ID'),
        ),
        migrations.AddField(
            model_name='message',
            name='related_object_type',
            field=models.CharField(blank=True, max_length=100, verbose_name='关联对象类型'),
        ),
        migrations.AddField(
            model_name='message',
            name='sender',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='notification_sent_messages', to=settings.AUTH_USER_MODEL, verbose_name='发送者'),
        ),
        migrations.AddField(
            model_name='message',
            name='target_departments',
            field=models.TextField(blank=True, default='', help_text='目标部门ID列表，JSON格式', verbose_name='目标部门'),
        ),
        migrations.AddField(
            model_name='message',
            name='target_users',
            field=models.TextField(blank=True, default='', help_text='目标用户ID列表，JSON格式', verbose_name='目标用户'),
        ),
        migrations.AddField(
            model_name='message',
            name='title',
            field=models.CharField(default='', max_length=200, verbose_name='消息标题'),
        ),
        migrations.AddField(
            model_name='message',
            name='action_url',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='跳转链接'),
        ),
        migrations.CreateModel(
            name='MessageUserRelation',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('is_read', models.BooleanField(default=False, verbose_name='是否已读')),
                ('is_starred', models.BooleanField(default=False, verbose_name='是否标星')),
                ('read_time', models.DateTimeField(blank=True, null=True, verbose_name='阅读时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('message', models.ForeignKey(on_delete=models.CASCADE, related_name='user_relations', to='message.message', verbose_name='消息')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='message_relations', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户消息关系',
                'verbose_name_plural': '用户消息关系',
                'db_table': 'message_user_relation',
                'unique_together': {('message', 'user')},
            },
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['created_at'], name='message_created_idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['is_active'], name='message_active_idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['related_object_type', 'related_object_id'], name='message_related_idx'),
        ),
        migrations.AddIndex(
            model_name='messageuserrelation',
            index=models.Index(fields=['user', 'is_read'], name='rel_user_read_idx'),
        ),
        migrations.AddIndex(
            model_name='messageuserrelation',
            index=models.Index(fields=['user', 'is_starred'], name='rel_user_star_idx'),
        ),
    ]
