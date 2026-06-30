from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contract", "0006_add_data_cross_check"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContractLegalConsultRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query_type", models.CharField(choices=[("consultation", "法律咨询"), ("knowledge", "知识查询")], default="consultation", max_length=20, verbose_name="查询类型")),
                ("question", models.TextField(default="", verbose_name="问题/查询内容")),
                ("context", models.TextField(blank=True, default="", verbose_name="补充上下文")),
                ("answer", models.TextField(default="", verbose_name="AI回复内容")),
                ("success", models.BooleanField(default=True, verbose_name="是否成功")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("contract", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="legal_consult_records", to="contract.contract", verbose_name="关联合同")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contract_legal_consult_records", to=settings.AUTH_USER_MODEL, verbose_name="咨询人")),
            ],
            options={
                "verbose_name": "AI法律咨询记录",
                "verbose_name_plural": "AI法律咨询记录",
                "db_table": "contract_legal_consult_record",
                "ordering": ["-created_at"],
            },
        ),
    ]
