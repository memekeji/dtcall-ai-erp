from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0006_customerfield_calculation_type'),
    ]

    operations = [
        migrations.AlterField(
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
                    ('formula', '公式计算'),
                ],
                default='',
                max_length=20,
                verbose_name='计算规则',
            ),
        ),
        migrations.AddField(
            model_name='customerfield',
            name='formula_expression',
            field=models.TextField(blank=True, default='', verbose_name='计算公式'),
        ),
    ]
