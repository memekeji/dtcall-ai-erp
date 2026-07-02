from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0004_add_customer_field_list_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerfield',
            name='relation_enabled',
            field=models.BooleanField(default=False, verbose_name='是否关联已有字段'),
        ),
        migrations.AddField(
            model_name='customerfield',
            name='related_field',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='linked_customer_fields', to='customer.customerfield', verbose_name='关联字段'),
        ),
        migrations.AddField(
            model_name='customerfield',
            name='relation_type',
            field=models.CharField(choices=[('bind', '关联绑定'), ('copy', '同步赋值')], default='bind', max_length=20, verbose_name='关联方式'),
        ),
    ]
