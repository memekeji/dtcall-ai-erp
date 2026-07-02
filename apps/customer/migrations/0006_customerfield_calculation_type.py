from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0005_customerfield_relations'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerfield',
            name='calculation_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('count', '统计数量'),
                    ('sum', '求和'),
                    ('avg', '平均值'),
                    ('max', '最大值'),
                    ('min', '最小值'),
                    ('concat', '文本拼接'),
                ],
                default='',
                max_length=20,
                verbose_name='计算规则',
            ),
        ),
    ]
