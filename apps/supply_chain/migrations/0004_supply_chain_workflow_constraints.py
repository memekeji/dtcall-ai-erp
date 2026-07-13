from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('supply_chain', '0003_production_readiness_foundation'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='demandforecastplan',
            constraint=models.UniqueConstraint(condition=models.Q(('source_id__isnull', False)), fields=('source_type', 'source_id'), name='supply_chain_unique_forecast_source'),
        ),
        migrations.AddConstraint(
            model_name='outsourceissueorder',
            constraint=models.UniqueConstraint(condition=models.Q(('source_id__isnull', False)), fields=('source_type', 'source_id'), name='supply_chain_unique_outsource_source'),
        ),
        migrations.AddConstraint(
            model_name='prreviewtask',
            constraint=models.UniqueConstraint(condition=models.Q(('source_id__isnull', False)), fields=('source_type', 'source_id'), name='supply_chain_unique_pr_source'),
        ),
        migrations.AddConstraint(
            model_name='pricerevieworder',
            constraint=models.UniqueConstraint(condition=models.Q(('source_id__isnull', False)), fields=('source_type', 'source_id'), name='supply_chain_unique_price_source'),
        ),
        migrations.AddConstraint(
            model_name='samplerequest',
            constraint=models.UniqueConstraint(condition=models.Q(('source_id__isnull', False)), fields=('source_type', 'source_id'), name='supply_chain_unique_sample_source'),
        ),
        migrations.AddConstraint(
            model_name='samplereceipt',
            constraint=models.UniqueConstraint(fields=('sample_request',), name='supply_chain_unique_sample_receipt'),
        ),
        migrations.AddConstraint(
            model_name='samplepickuprecord',
            constraint=models.UniqueConstraint(fields=('sample_request',), name='supply_chain_unique_sample_pickup'),
        ),
    ]
