from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0003_customer_ai_intent_tags_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerfield',
            name='field_type',
            field=models.CharField(
                choices=[
                    ('text', '单行文本'),
                    ('number', '数字'),
                    ('date', '日期'),
                    ('datetime', '日期时间'),
                    ('textarea', '多行文本'),
                    ('list', '列表'),
                    ('select', '下拉选择'),
                    ('checkbox', '复选框'),
                    ('radio', '单选框'),
                ],
                max_length=20,
                verbose_name='字段类型',
            ),
        ),
    ]
