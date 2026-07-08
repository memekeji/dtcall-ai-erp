"""
财务管理模块服务层
封装当前财务模型可用的业务能力。
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    AccountsPayable,
    AccountsReceivable,
    BankReconciliation,
    BankTransaction,
    CostAllocation,
    Expense,
    FinanceAccount,
    FinanceBudget,
    FinanceStatus,
    FinancialPeriodClose,
    FinancialReport,
    ChartOfAccount,
    LedgerVoucherLine,
    CashFlowPlan,
    FinancialRatio,
    ExpenseAccrual,
    FixedAsset,
    Income,
    Invoice,
    InvoiceRequest,
    InvoiceVerifyRecord,
    LedgerVoucher,
    OrderFinanceRecord,
    Payment,
    TaxRecord,
)


def normalize_datetime_value(value):
    """统一处理日期时间，避免测试环境和运行环境的时区差异。"""
    if not value:
        return timezone.now().replace(tzinfo=None)
    if isinstance(value, str):
        value = parse_datetime(value) or timezone.now().replace(tzinfo=None)
    if getattr(value, "tzinfo", None) is not None:
        value = value.replace(tzinfo=None)
    return value


def update_account_balance(account_id: int, amount: Decimal, direction: str) -> None:
    if not account_id:
        return
    account = FinanceAccount.objects.select_for_update().filter(id=account_id).first()
    if not account:
        return
    change = amount if direction == "in" else -amount
    account.current_balance = (account.current_balance or Decimal("0")) + change
    account.save(update_fields=["current_balance"])


def create_bank_transaction_entry(
    *,
    account_id: int,
    transaction_date,
    direction: str,
    amount: Decimal,
    counterparty: str,
    related_type: str,
    related_id: int,
    purpose: str = "",
    transaction_no: str = "",
    match_status: str = "matched",
    remark: str = "",
):
    if not account_id:
        return None
    with transaction.atomic():
        existing = BankTransaction.objects.filter(
            related_type=related_type,
            related_id=related_id,
            account_id=account_id,
        ).first()
        if existing:
            return existing
        transaction_obj = BankTransaction.objects.create(
            account_id=account_id,
            transaction_date=normalize_datetime_value(transaction_date),
            direction=direction,
            amount=amount,
            counterparty=counterparty,
            transaction_no=transaction_no,
            purpose=purpose,
            match_status=match_status,
            related_type=related_type,
            related_id=related_id,
            create_time=int(timezone.now().timestamp()),
            remark=remark,
        )
        update_account_balance(account_id, amount, direction)
        return transaction_obj


def _normalize_datetime(value):
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        if isinstance(value, datetime):
            return normalize_datetime_value(value)
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and " " not in value and "T" not in value:
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            pass
    return normalize_datetime_value(value)


class FinanceLinkageService:
    """财务与业务模块联动服务。"""

    @staticmethod
    def get_default_user():
        from apps.user.models import Admin

        return Admin.objects.order_by("id").first()

    @staticmethod
    def ensure_order_finance_record(order) -> OrderFinanceRecord:
        if order is None:
            raise ValueError("订单不能为空")
        due_date = None
        if getattr(order, "order_date", None):
            due_date = order.order_date + timedelta(days=30)
        finance_record, _ = OrderFinanceRecord.objects.get_or_create(
            order_id=order.id,
            defaults={
                "total_amount": order.amount,
                "paid_amount": Decimal("0"),
                "payment_status": "pending",
                "due_date": due_date,
                "create_time": int(timezone.now().timestamp()),
                "remark": "",
            },
        )
        updated_fields = []
        if finance_record.total_amount != order.amount:
            finance_record.total_amount = order.amount
            updated_fields.append("total_amount")
        if due_date and finance_record.due_date != due_date:
            finance_record.due_date = due_date
            updated_fields.append("due_date")
        payment_status = (
            "paid"
            if finance_record.paid_amount >= finance_record.total_amount
            else "partial"
            if finance_record.paid_amount > 0
            else "pending"
        )
        if finance_record.payment_status != payment_status:
            finance_record.payment_status = payment_status
            updated_fields.append("payment_status")
        if updated_fields:
            finance_record.save(update_fields=updated_fields)
        if getattr(order, "finance_status", "") != "synced":
            order.finance_status = "synced"
            order.save(update_fields=["finance_status"])
        return finance_record

    @staticmethod
    def apply_payment_to_order(payment: Payment) -> None:
        if not payment.order_id:
            return
        from apps.customer.models import CustomerOrder

        order = CustomerOrder.objects.filter(id=payment.order_id).first()
        if not order:
            return
        finance_record = FinanceLinkageService.ensure_order_finance_record(order)
        paid_amount = (
            Payment.objects.filter(order_id=order.id).aggregate(total=Sum("amount"))[
                "total"
            ]
            or Decimal("0")
        )
        finance_record.paid_amount = min(paid_amount, finance_record.total_amount)
        if finance_record.paid_amount <= 0:
            finance_record.payment_status = "pending"
        elif finance_record.paid_amount < finance_record.total_amount:
            finance_record.payment_status = "partial"
        else:
            finance_record.payment_status = "paid"
        finance_record.save(update_fields=["paid_amount", "payment_status"])

    @staticmethod
    def ensure_receivable_for_invoice(invoice: Invoice, order_id: int = 0) -> AccountsReceivable:
        receivable, _ = AccountsReceivable.objects.get_or_create(
            invoice_id=invoice.id,
            defaults={
                "code": invoice.code or f"AR-{invoice.id}",
                "customer_id": invoice.customer_id,
                "order_id": order_id,
                "amount": invoice.amount,
                "received_amount": Decimal("0"),
                "status": "pending",
                "create_time": int(timezone.now().timestamp()),
                "remark": invoice.remark,
            },
        )
        updated_fields = []
        if receivable.customer_id != invoice.customer_id:
            receivable.customer_id = invoice.customer_id
            updated_fields.append("customer_id")
        if order_id and receivable.order_id != order_id:
            receivable.order_id = order_id
            updated_fields.append("order_id")
        if receivable.amount != invoice.amount:
            receivable.amount = invoice.amount
            updated_fields.append("amount")
        if updated_fields:
            receivable.save(update_fields=updated_fields)
        return receivable

    @staticmethod
    def refresh_receivable_for_invoice(invoice: Invoice, order_id: int = 0) -> None:
        receivable = FinanceLinkageService.ensure_receivable_for_invoice(
            invoice, order_id=order_id
        )
        receivable.received_amount = invoice.enter_amount
        if receivable.received_amount <= 0:
            receivable.status = "pending"
        elif receivable.received_amount < receivable.amount:
            receivable.status = "partial"
        else:
            receivable.status = "settled"
        receivable.save(update_fields=["received_amount", "status"])


class BankTransactionService:
    """银行流水联动、导入与对账服务。"""

    TRANSACTION_FIELD_ALIASES = {
        "transaction_no": ["transaction_no", "流水号", "交易流水号"],
        "transaction_date": ["transaction_date", "交易时间", "交易日期"],
        "direction": ["direction", "收支方向", "借贷方向"],
        "amount": ["amount", "交易金额", "金额"],
        "counterparty": ["counterparty", "交易对方", "对方户名", "客户名称", "供应商名称"],
        "purpose": ["purpose", "用途", "摘要", "备注"],
        "customer_name": ["customer_name", "客户", "客户名称"],
        "supplier_name": ["supplier_name", "供应商", "供应商名称"],
        "order_number": ["order_number", "订单编号", "客户订单"],
        "contract_number": ["contract_number", "合同编号", "合同号"],
        "invoice_code": ["invoice_code", "发票号", "发票编号"],
    }

    @staticmethod
    def resolve_account(account_id: int = 0) -> FinanceAccount:
        queryset = FinanceAccount.objects.filter(status="active").order_by("id")
        account = queryset.filter(id=account_id).first() if account_id else queryset.first()
        if not account:
            raise ValueError("未找到可用的资金账户")
        return account

    @staticmethod
    def _row_value(row: Dict, key: str, default=""):
        aliases = BankTransactionService.TRANSACTION_FIELD_ALIASES.get(key, [key])
        for alias in aliases:
            value = row.get(alias)
            if value not in (None, ""):
                return value
        return default

    @staticmethod
    def normalize_row(row: Dict) -> Dict:
        amount = Decimal(str(BankTransactionService._row_value(row, "amount", "0")))
        direction = str(BankTransactionService._row_value(row, "direction", "")).strip().lower()
        if direction in {"收入", "贷", "贷方", "in"}:
            direction = "in"
        elif direction in {"支出", "借", "借方", "out"}:
            direction = "out"
        elif amount < 0:
            direction = "out"
            amount = abs(amount)
        else:
            direction = "in"
        return {
            "transaction_no": str(
                BankTransactionService._row_value(row, "transaction_no", "")
            ).strip(),
            "transaction_date": _normalize_datetime(
                BankTransactionService._row_value(row, "transaction_date")
            ),
            "direction": direction,
            "amount": amount,
            "counterparty": str(
                BankTransactionService._row_value(row, "counterparty", "")
            ).strip(),
            "purpose": str(BankTransactionService._row_value(row, "purpose", "")).strip(),
            "customer_name": str(
                BankTransactionService._row_value(row, "customer_name", "")
            ).strip(),
            "supplier_name": str(
                BankTransactionService._row_value(row, "supplier_name", "")
            ).strip(),
            "order_number": str(
                BankTransactionService._row_value(row, "order_number", "")
            ).strip(),
            "contract_number": str(
                BankTransactionService._row_value(row, "contract_number", "")
            ).strip(),
            "invoice_code": str(
                BankTransactionService._row_value(row, "invoice_code", "")
            ).strip(),
        }

    @staticmethod
    def create_or_update_transaction(
        *,
        account: FinanceAccount,
        transaction_date,
        direction: str,
        amount: Decimal,
        counterparty: str,
        purpose: str,
        related_type: str,
        related_id: int,
        match_status: str = "matched",
        transaction_no: str = "",
        remark: str = "",
    ) -> BankTransaction:
        with transaction.atomic():
            existing = (
                BankTransaction.objects.select_for_update()
                .filter(related_type=related_type, related_id=related_id)
                .first()
            )
            if existing:
                if existing.account_id != account.id:
                    AdvancedFinanceService.apply_account_balance(
                        existing.account_id,
                        existing.amount,
                        existing.direction,
                        reverse=True,
                    )
                    existing.account = account
                if (
                    existing.amount != amount
                    or existing.direction != direction
                    or existing.transaction_date != transaction_date
                ):
                    AdvancedFinanceService.apply_account_balance(
                        existing.account_id,
                        existing.amount,
                        existing.direction,
                        reverse=True,
                    )
                    existing.amount = amount
                    existing.direction = direction
                    existing.transaction_date = transaction_date
                    AdvancedFinanceService.apply_account_balance(
                        account.id, amount, direction
                    )
                existing.counterparty = counterparty
                existing.purpose = purpose
                existing.match_status = match_status
                existing.transaction_no = transaction_no
                existing.remark = remark
                existing.save()
                return existing

            instance = BankTransaction.objects.create(
                account=account,
                transaction_date=transaction_date,
                direction=direction,
                amount=amount,
                counterparty=counterparty,
                purpose=purpose,
                match_status=match_status,
                related_type=related_type,
                related_id=related_id,
                transaction_no=transaction_no,
                create_time=int(timezone.now().timestamp()),
                remark=remark,
            )
            AdvancedFinanceService.apply_account_balance(account.id, amount, direction)
            return instance

    @staticmethod
    def delete_related_transaction(related_type: str, related_id: int) -> None:
        bank_transaction = (
            BankTransaction.objects.filter(related_type=related_type, related_id=related_id)
            .order_by("-id")
            .first()
        )
        if bank_transaction:
            AdvancedFinanceService.delete_bank_transaction(bank_transaction)

    @staticmethod
    def create_for_income(income: Income, account_id: int = 0) -> Optional[BankTransaction]:
        try:
            account = BankTransactionService.resolve_account(account_id)
        except ValueError:
            return None
        invoice = Invoice.objects.filter(id=income.invoice_id).first()
        counterparty = invoice.invoice_title if invoice else ""
        if not counterparty and invoice and invoice.customer_id:
            from apps.customer.models import Customer

            customer = Customer.objects.filter(id=invoice.customer_id).first()
            counterparty = customer.name if customer else ""
        return BankTransactionService.create_or_update_transaction(
            account=account,
            transaction_date=income.income_date,
            direction="in",
            amount=income.amount,
            counterparty=counterparty,
            purpose=income.remark or "回款",
            related_type="income",
            related_id=income.id,
            match_status="matched",
            transaction_no=f"INC-{income.id}",
        )

    @staticmethod
    def create_for_payment(payment: Payment, account_id: int = 0) -> Optional[BankTransaction]:
        try:
            account = BankTransactionService.resolve_account(account_id)
        except ValueError:
            return None
        counterparty = ""
        if payment.customer_id:
            from apps.customer.models import Customer

            customer = Customer.objects.filter(id=payment.customer_id).first()
            counterparty = customer.name if customer else ""
        return BankTransactionService.create_or_update_transaction(
            account=account,
            transaction_date=payment.payment_date,
            direction="out",
            amount=payment.amount,
            counterparty=counterparty,
            purpose=payment.remark or "付款",
            related_type="payment",
            related_id=payment.id,
            match_status="matched",
            transaction_no=f"PAY-{payment.id}",
        )

    @staticmethod
    def ensure_business_links(normalized_row: Dict, auto_create_related: bool = False, user=None):
        from apps.contract.models import Contract, Supplier
        from apps.customer.models import Customer, CustomerContract, CustomerOrder

        default_user = user or FinanceLinkageService.get_default_user()
        customer = None
        supplier = None
        customer_contract = None
        legacy_contract = None
        order = None
        invoice = None

        customer_name = normalized_row["customer_name"] or (
            normalized_row["counterparty"] if normalized_row["direction"] == "in" else ""
        )
        if customer_name:
            customer = Customer.objects.filter(name=customer_name, delete_time=0).first()
            if not customer and auto_create_related:
                customer = Customer.objects.create(
                    name=customer_name,
                    belong_uid=getattr(default_user, "id", 0) or 0,
                    admin_id=getattr(default_user, "id", 0) or 0,
                    delete_time=0,
                )

        supplier_name = normalized_row["supplier_name"] or (
            normalized_row["counterparty"] if normalized_row["direction"] == "out" else ""
        )
        if supplier_name:
            supplier = Supplier.objects.filter(name=supplier_name).first()
            if not supplier and auto_create_related:
                supplier = Supplier.objects.create(
                    name=supplier_name,
                    code=f"SUP-{supplier_name[:20]}-{Supplier.objects.count() + 1}",
                    contact_person=supplier_name[:20] or "导入",
                    contact_phone="",
                )

        if normalized_row["contract_number"]:
            customer_contract = CustomerContract.objects.filter(
                contract_number=normalized_row["contract_number"]
            ).first()
            if not customer_contract and auto_create_related and customer and default_user:
                customer_contract = CustomerContract.objects.create(
                    customer=customer,
                    contract_number=normalized_row["contract_number"],
                    name=normalized_row["contract_number"],
                    amount=normalized_row["amount"],
                    sign_date=normalized_row["transaction_date"].date(),
                    status="signed",
                    create_user=default_user,
                    delete_time=0,
                    auto_generated=True,
                )
            legacy_contract = Contract.objects.filter(
                code=normalized_row["contract_number"], delete_time=0
            ).first()
            if not legacy_contract and auto_create_related:
                legacy_contract = Contract.objects.create(
                    code=normalized_row["contract_number"],
                    name=normalized_row["contract_number"],
                    customer_id=customer.id if customer else 0,
                    customer=customer.name if customer else "",
                    sign_time=int(normalized_row["transaction_date"].timestamp()),
                    cost=normalized_row["amount"],
                    admin_id=getattr(default_user, "id", 0) or 0,
                    auto_generated=True,
                )

        if normalized_row["order_number"]:
            order = CustomerOrder.objects.filter(
                order_number=normalized_row["order_number"], delete_time=0
            ).first()
            if not order and auto_create_related and customer and default_user:
                order = CustomerOrder.objects.create(
                    customer=customer,
                    contract=customer_contract,
                    order_number=normalized_row["order_number"],
                    product_name=normalized_row["purpose"] or "银行流水导入",
                    amount=normalized_row["amount"],
                    order_date=normalized_row["transaction_date"].date(),
                    status="confirmed",
                    create_user=default_user,
                    delete_time=0,
                    auto_generated=True,
                )
            if order:
                FinanceLinkageService.ensure_order_finance_record(order)

        if normalized_row["invoice_code"]:
            invoice = Invoice.objects.filter(code=normalized_row["invoice_code"]).first()
            if not invoice and auto_create_related:
                invoice = Invoice.objects.create(
                    code=normalized_row["invoice_code"],
                    customer_id=customer.id if customer else 0,
                    contract_id=legacy_contract.id if legacy_contract else 0,
                    amount=normalized_row["amount"],
                    admin_id=getattr(default_user, "id", 0) or 0,
                    open_status=FinanceStatus.INVOICE_OPEN_STATUS_DONE
                    if normalized_row["direction"] == "in"
                    else FinanceStatus.INVOICE_OPEN_STATUS_NOT,
                    invoice_type=2,
                    invoice_title=customer.name if customer else normalized_row["counterparty"],
                    create_time=int(timezone.now().timestamp()),
                    remark=normalized_row["purpose"],
                )
            if invoice:
                FinanceLinkageService.ensure_receivable_for_invoice(
                    invoice, order_id=order.id if order else 0
                )

        return {
            "customer": customer,
            "supplier": supplier,
            "customer_contract": customer_contract,
            "legacy_contract": legacy_contract,
            "order": order,
            "invoice": invoice,
        }

    @staticmethod
    def _find_duplicate_transaction(account_id: int, normalized_row: Dict):
        queryset = BankTransaction.objects.filter(account_id=account_id)
        if normalized_row["transaction_no"]:
            duplicate = queryset.filter(
                transaction_no=normalized_row["transaction_no"]
            ).first()
            if duplicate:
                return duplicate
        base_queryset = queryset.filter(
            transaction_date=normalized_row["transaction_date"],
            direction=normalized_row["direction"],
            amount=normalized_row["amount"],
        )
        if normalized_row["counterparty"]:
            duplicate = base_queryset.filter(
                counterparty=normalized_row["counterparty"]
            ).first()
            if duplicate:
                return duplicate
        if normalized_row["purpose"]:
            duplicate = base_queryset.filter(purpose=normalized_row["purpose"]).first()
            if duplicate:
                return duplicate
        return base_queryset.first()

    @staticmethod
    def import_transactions(account_id: int, rows: List[Dict], auto_create_related: bool = False, user=None) -> Dict:
        account = BankTransactionService.resolve_account(account_id)
        created_count = 0
        skipped_count = 0
        items = []
        for row in rows:
            normalized = BankTransactionService.normalize_row(row)
            duplicate = BankTransactionService._find_duplicate_transaction(account.id, normalized)
            if duplicate:
                skipped_count += 1
                items.append(
                    {
                        "transaction_no": normalized["transaction_no"],
                        "status": "skipped",
                        "bank_transaction_id": duplicate.id,
                    }
                )
                continue
            links = BankTransactionService.ensure_business_links(
                normalized, auto_create_related=auto_create_related, user=user
            )
            related_type = ""
            related_id = 0
            if links["invoice"]:
                related_type = "invoice"
                related_id = links["invoice"].id
            elif links["order"]:
                related_type = "order"
                related_id = links["order"].id
            elif links["supplier"]:
                related_type = "supplier"
                related_id = links["supplier"].id
            elif links["customer"]:
                related_type = "customer"
                related_id = links["customer"].id
            bank_transaction = BankTransaction.objects.create(
                account=account,
                transaction_date=normalized["transaction_date"],
                direction=normalized["direction"],
                amount=normalized["amount"],
                counterparty=normalized["counterparty"],
                transaction_no=normalized["transaction_no"],
                purpose=normalized["purpose"],
                match_status="matched" if related_type else "unmatched",
                related_type=related_type,
                related_id=related_id,
                create_time=int(timezone.now().timestamp()),
                remark="导入创建",
            )
            AdvancedFinanceService.apply_account_balance(
                account.id, normalized["amount"], normalized["direction"]
            )
            created_count += 1
            items.append(
                {
                    "transaction_no": normalized["transaction_no"],
                    "status": "created",
                    "bank_transaction_id": bank_transaction.id,
                }
            )
        return {
            "created_count": created_count,
            "skipped_count": skipped_count,
            "items": items,
        }

    @staticmethod
    def build_system_candidates(normalized_row: Dict) -> List[Dict]:
        candidates = []
        if normalized_row["invoice_code"]:
            invoice = Invoice.objects.filter(code=normalized_row["invoice_code"]).first()
            if invoice:
                candidates.append(
                    {
                        "record_type": "invoice",
                        "id": invoice.id,
                        "code": invoice.code,
                        "amount": float(invoice.amount),
                        "customer_id": invoice.customer_id,
                    }
                )
                incomes = Income.objects.filter(invoice_id=invoice.id).order_by("-income_date")[:5]
                for income in incomes:
                    candidates.append(
                        {
                            "record_type": "income",
                            "id": income.id,
                            "amount": float(income.amount),
                            "date": income.income_date.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
        if normalized_row["order_number"]:
            from apps.customer.models import CustomerOrder

            order = CustomerOrder.objects.filter(
                order_number=normalized_row["order_number"], delete_time=0
            ).first()
            if order:
                candidates.append(
                    {
                        "record_type": "order",
                        "id": order.id,
                        "code": order.order_number,
                        "amount": float(order.amount),
                    }
                )
        if normalized_row["counterparty"]:
            payment_qs = Payment.objects.filter(amount=normalized_row["amount"]).order_by("-payment_date")[:5]
            for payment in payment_qs:
                candidates.append(
                    {
                        "record_type": "payment",
                        "id": payment.id,
                        "amount": float(payment.amount),
                        "date": payment.payment_date.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
        return candidates

    @staticmethod
    def import_reconciliation(
        account_id: int,
        period: str,
        rows: List[Dict],
        bank_balance=None,
    ) -> Dict:
        account = BankTransactionService.resolve_account(account_id)
        matched_count = 0
        mismatch_count = 0
        items = []
        for row in rows:
            normalized = BankTransactionService.normalize_row(row)
            matched_transaction = BankTransactionService._find_duplicate_transaction(
                account.id, normalized
            )
            system_records = BankTransactionService.build_system_candidates(normalized)
            status = "matched" if matched_transaction else "mismatch"
            if status == "matched":
                matched_count += 1
            else:
                mismatch_count += 1
                if not system_records:
                    fallback = (
                        BankTransaction.objects.filter(account_id=account.id)
                        .order_by("-transaction_date")[:5]
                    )
                    system_records = [
                        {
                            "record_type": "bank_transaction",
                            "id": item.id,
                            "amount": float(item.amount),
                            "transaction_no": item.transaction_no,
                        }
                        for item in fallback
                    ]
            items.append(
                {
                    "transaction_no": normalized["transaction_no"],
                    "status": status,
                    "imported": {
                        "transaction_date": normalized["transaction_date"].strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "direction": normalized["direction"],
                        "amount": float(normalized["amount"]),
                        "counterparty": normalized["counterparty"],
                        "invoice_code": normalized["invoice_code"],
                        "order_number": normalized["order_number"],
                    },
                    "bank_transaction_id": matched_transaction.id if matched_transaction else 0,
                    "system_records": system_records,
                }
            )
        book_balance = account.current_balance or Decimal("0")
        bank_balance_decimal = Decimal(str(bank_balance if bank_balance is not None else book_balance))
        reconciliation, _ = BankReconciliation.objects.get_or_create(
            account=account,
            period=period,
            defaults={"create_time": int(timezone.now().timestamp())},
        )
        reconciliation.book_balance = book_balance
        reconciliation.bank_balance = bank_balance_decimal
        reconciliation.difference_amount = bank_balance_decimal - book_balance
        reconciliation.status = (
            "balanced"
            if reconciliation.difference_amount == Decimal("0") and mismatch_count == 0
            else "difference"
        )
        reconciliation.reconciled_time = int(timezone.now().timestamp())
        reconciliation.remark = json.dumps(
            {
                "summary": {
                    "matched_count": matched_count,
                    "mismatch_count": mismatch_count,
                    "total_count": len(items),
                },
                "items": items,
            },
            ensure_ascii=False,
        )
        reconciliation.save()
        return {
            "reconciliation_id": reconciliation.id,
            "summary": {
                "matched_count": matched_count,
                "mismatch_count": mismatch_count,
                "total_count": len(items),
            },
        }

    @staticmethod
    def get_reconciliation_detail(reconciliation: BankReconciliation) -> Dict:
        if not reconciliation.remark:
            return {"summary": {}, "items": []}
        try:
            return json.loads(reconciliation.remark)
        except json.JSONDecodeError:
            return {"summary": {}, "items": []}


class ExpenseService:
    """报销服务类"""

    @staticmethod
    def mark_paid(
        expense_id: int,
        user,
        amount: Decimal,
        payment_date=None,
        file_ids: str = "",
        remark: str = "",
        customer_id: int = 0,
        order_id: int = 0,
        purchase_order_id: int = 0,
        purchase_contract_id: int = 0,
        project_id: int = 0,
    ) -> Tuple[bool, str, Payment]:
        """登记报销付款并更新报销付款状态。"""
        try:
            expense = Expense.objects.get(id=expense_id)
        except Expense.DoesNotExist:
            return False, "报销单不存在", None

        if expense.check_status != FinanceStatus.EXPENSE_CHECK_APPROVED:
            return False, "仅审核通过的报销允许付款", None

        with transaction.atomic():
            payment_dt = _normalize_datetime(payment_date)
            payment = Payment.objects.create(
                expense_id=expense.id,
                customer_id=customer_id,
                order_id=order_id,
                purchase_order_id=purchase_order_id,
                purchase_contract_id=purchase_contract_id,
                project_id=project_id,
                amount=amount,
                payment_date=payment_dt,
                file_ids=file_ids,
                remark=remark,
                create_time=int(timezone.now().timestamp()),
            )
            expense.pay_status = FinanceStatus.PAY_STATUS_PAID
            expense.pay_admin_id = getattr(user, "id", 0) or 0
            expense.pay_time = int(payment_dt.timestamp())
            expense.save(update_fields=["pay_status", "pay_admin_id", "pay_time"])

        return True, "付款成功", payment

    @staticmethod
    def get_expense_statistics(start_ts=None, end_ts=None) -> Dict:
        queryset = Expense.objects.all()
        if start_ts:
            queryset = queryset.filter(expense_time__gte=start_ts)
        if end_ts:
            queryset = queryset.filter(expense_time__lte=end_ts)

        stats = queryset.aggregate(total_count=Count("id"), total_amount=Sum("cost"))
        paid_amount = Payment.objects.filter(
            expense_id__in=queryset.values("id")
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(stats["total_amount"] or Decimal("0")),
            "approved_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_APPROVED
            ).count(),
            "pending_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_PENDING
            ).count(),
            "processing_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_PROCESSING
            ).count(),
            "rejected_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_REJECTED
            ).count(),
            "paid_amount": float(paid_amount),
            "unpaid_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
                pay_status=FinanceStatus.PAY_STATUS_PENDING,
            ).count(),
        }

    @staticmethod
    def batch_approve(expense_ids: List[int], user, action: str) -> Tuple[int, int]:
        expenses = Expense.objects.filter(
            id__in=expense_ids, check_status=FinanceStatus.EXPENSE_CHECK_PROCESSING
        )
        success_count = 0
        fail_count = 0
        now_ts = int(timezone.now().timestamp())

        for expense in expenses:
            if action == "approve":
                expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
                expense.check_time = now_ts
            else:
                expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED
            expense.check_history_uids = (
                f"{expense.check_history_uids},{user.id}"
                if expense.check_history_uids
                else str(user.id)
            )
            expense.save(
                update_fields=["check_status", "check_time", "check_history_uids"]
            )
            success_count += 1

        fail_count = len(expense_ids) - success_count
        return success_count, fail_count


class InvoiceService:
    """发票服务类"""

    @staticmethod
    def issue_invoice(invoice_id: int, user) -> Tuple[bool, str]:
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return False, "发票不存在"

        if invoice.open_status == FinanceStatus.INVOICE_OPEN_STATUS_DONE:
            return False, "发票已开具"

        invoice.open_status = FinanceStatus.INVOICE_OPEN_STATUS_DONE
        invoice.open_admin_id = getattr(user, "id", 0) or 0
        invoice.open_time = int(timezone.now().timestamp())
        invoice.save(update_fields=["open_status", "open_admin_id", "open_time"])
        return True, "开票成功"

    @staticmethod
    def refresh_income_status(invoice: Invoice) -> Invoice:
        paid_amount = Income.objects.filter(invoice_id=invoice.id).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        invoice.enter_amount = min(paid_amount, invoice.amount)
        if invoice.enter_amount <= 0:
            invoice.enter_status = FinanceStatus.ENTER_STATUS_NOT
        elif invoice.enter_amount < invoice.amount:
            invoice.enter_status = FinanceStatus.ENTER_STATUS_PARTIAL
        else:
            invoice.enter_status = FinanceStatus.ENTER_STATUS_FULL
        latest_income = (
            Income.objects.filter(invoice_id=invoice.id)
            .order_by("-income_date")
            .first()
        )
        invoice.enter_time = (
            int(latest_income.income_date.timestamp()) if latest_income else 0
        )
        invoice.save(update_fields=["enter_amount", "enter_status", "enter_time"])
        FinanceLinkageService.refresh_receivable_for_invoice(invoice)
        return invoice

    @staticmethod
    def get_invoice_statistics(start_ts=None, end_ts=None) -> Dict:
        queryset = Invoice.objects.all()
        if start_ts:
            queryset = queryset.filter(create_time__gte=start_ts)
        if end_ts:
            queryset = queryset.filter(create_time__lte=end_ts)

        stats = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            enter_amount=Sum("enter_amount"),
        )
        total_amount = stats["total_amount"] or Decimal("0")
        enter_amount = stats["enter_amount"] or Decimal("0")

        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(total_amount),
            "enter_amount": float(enter_amount),
            "uncollected_amount": float(max(total_amount - enter_amount, Decimal("0"))),
            "not_open_count": queryset.filter(
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_NOT
            ).count(),
            "opened_count": queryset.filter(
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_DONE
            ).count(),
            "void_count": queryset.filter(
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_VOID
            ).count(),
            "unpaid_count": queryset.filter(
                enter_status=FinanceStatus.ENTER_STATUS_NOT
            ).count(),
            "partial_count": queryset.filter(
                enter_status=FinanceStatus.ENTER_STATUS_PARTIAL
            ).count(),
            "paid_count": queryset.filter(
                enter_status=FinanceStatus.ENTER_STATUS_FULL
            ).count(),
        }


class IncomeService:
    """回款服务类"""

    @staticmethod
    def create_income(data: Dict) -> Income:
        with transaction.atomic():
            income = Income.objects.create(
                invoice_id=data.get("invoice_id") or 0,
                amount=Decimal(str(data.get("amount") or 0)),
                income_date=_normalize_datetime(data.get("income_date")),
                file_ids=data.get("file_ids", ""),
                remark=data.get("remark", ""),
                create_time=int(timezone.now().timestamp()),
            )
            if income.invoice_id:
                invoice = Invoice.objects.filter(id=income.invoice_id).first()
                if invoice:
                    InvoiceService.refresh_income_status(invoice)
            BankTransactionService.create_for_income(
                income, int(data.get("account_id") or 0)
            )
            return income

    @staticmethod
    def delete_income(income: Income) -> None:
        invoice_id = income.invoice_id
        with transaction.atomic():
            BankTransactionService.delete_related_transaction("income", income.id)
            income.delete()
            if invoice_id:
                invoice = Invoice.objects.filter(id=invoice_id).first()
                if invoice:
                    InvoiceService.refresh_income_status(invoice)

    @staticmethod
    def verify_income(income_id: int, verify_data: List[Dict]) -> Tuple[bool, str]:
        try:
            income = Income.objects.get(id=income_id)
        except Income.DoesNotExist:
            return False, "回款记录不存在"

        total_verify = sum(Decimal(str(item.get("amount", 0))) for item in verify_data)
        if total_verify > income.amount:
            return False, "核销金额超出回款金额"

        with transaction.atomic():
            for item in verify_data:
                invoice_id = item.get("invoice_id")
                amount = Decimal(str(item.get("amount", 0)))
                if not invoice_id or amount <= 0:
                    continue
                invoice = (
                    Invoice.objects.select_for_update().filter(id=invoice_id).first()
                )
                if not invoice:
                    continue
                InvoiceVerifyRecord.objects.create(
                    invoice_id=invoice.id,
                    income=income,
                    amount=amount,
                    create_time=int(timezone.now().timestamp()),
                )
                InvoiceService.refresh_income_status(invoice)

        return True, "核销成功"

    @staticmethod
    def get_income_statistics(start_date=None, end_date=None) -> Dict:
        queryset = Income.objects.all()
        if start_date:
            queryset = queryset.filter(income_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(income_date__lte=end_date)
        stats = queryset.aggregate(total_count=Count("id"), total_amount=Sum("amount"))
        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(stats["total_amount"] or Decimal("0")),
        }


class PaymentService:
    """付款服务类"""

    @staticmethod
    def create_payment(data: Dict, user=None) -> Payment:
        payment_date = _normalize_datetime(data.get("payment_date"))
        expense_id = int(data.get("expense_id") or 0)
        customer_id = int(data.get("customer_id") or 0)
        order_id = int(data.get("order_id") or 0)
        purchase_order_id = int(data.get("purchase_order_id") or 0)
        purchase_contract_id = int(data.get("purchase_contract_id") or 0)
        project_id = int(data.get("project_id") or 0)
        amount = Decimal(str(data.get("amount") or 0))
        if not any(
            [
                expense_id,
                customer_id,
                order_id,
                purchase_order_id,
                purchase_contract_id,
                project_id,
            ]
        ):
            raise ValueError("至少关联一项业务对象")

        if order_id and not customer_id:
            from apps.customer.models import CustomerOrder

            order = CustomerOrder.objects.filter(id=order_id).first()
            if order and order.customer_id:
                customer_id = order.customer_id

        if project_id and not customer_id:
            from apps.project.models import Project

            project = Project.objects.filter(id=project_id).first()
            if project and project.customer_id:
                customer_id = project.customer_id

        expense = Expense.objects.filter(id=expense_id).first() if expense_id else None
        if expense:
            success, message, payment = ExpenseService.mark_paid(
                expense.id,
                user,
                amount,
                payment_date=payment_date,
                file_ids=data.get("file_ids", ""),
                remark=data.get("remark", ""),
                customer_id=customer_id,
                order_id=order_id,
                purchase_order_id=purchase_order_id,
                purchase_contract_id=purchase_contract_id,
                project_id=project_id,
            )
            if not success:
                raise ValueError(message)
            BankTransactionService.create_for_payment(
                payment, int(data.get("account_id") or 0)
            )
            FinanceLinkageService.apply_payment_to_order(payment)
            return payment

        payment = Payment.objects.create(
            expense_id=expense_id,
            customer_id=customer_id,
            order_id=order_id,
            purchase_order_id=purchase_order_id,
            purchase_contract_id=purchase_contract_id,
            project_id=project_id,
            amount=amount,
            payment_date=payment_date,
            file_ids=data.get("file_ids", ""),
            remark=data.get("remark", ""),
            create_time=int(timezone.now().timestamp()),
        )
        BankTransactionService.create_for_payment(payment, int(data.get("account_id") or 0))
        FinanceLinkageService.apply_payment_to_order(payment)
        return payment

    @staticmethod
    def get_payment_statistics(start_date=None, end_date=None) -> Dict:
        queryset = Payment.objects.all()
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        stats = queryset.aggregate(total_count=Count("id"), total_amount=Sum("amount"))
        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(stats["total_amount"] or Decimal("0")),
        }


class InvoiceRequestService:
    """开票申请服务类"""

    @staticmethod
    def approve_request(
        request_id: int, user, action: str, comment: str = ""
    ) -> Tuple[bool, str]:
        try:
            request = InvoiceRequest.objects.get(id=request_id)
        except InvoiceRequest.DoesNotExist:
            return False, "申请不存在"

        if request.status != "pending":
            return False, "该申请已被处理"

        from apps.customer.models import CustomerOrder

        order = CustomerOrder.objects.select_related("customer").filter(id=request.order_id).first()

        request.status = action
        request.reviewer_id = getattr(user, "id", 0) or 0
        request.review_time = int(timezone.now().timestamp())
        request.review_comment = comment
        request.save(
            update_fields=["status", "reviewer_id", "review_time", "review_comment"]
        )

        if action == "approved":
            invoice = Invoice.objects.create(
                customer_id=order.customer_id if order and order.customer_id else 0,
                contract_id=getattr(order.contract, "id", 0) if order and getattr(order, "contract_id", 0) else 0,
                amount=request.amount,
                admin_id=request.applicant_id,
                invoice_type=request.invoice_type,
                invoice_title=request.invoice_title,
                invoice_tax=request.tax_number,
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_NOT,
                create_time=int(timezone.now().timestamp()),
                remark=request.reason,
            )
            request.invoice_id = invoice.id
            request.invoice_time = int(timezone.now().timestamp())
            request.status = "invoiced"
            request.save(update_fields=["invoice_id", "invoice_time", "status"])
            CustomerOrder.objects.filter(id=request.order_id).update(
                invoice_request_status="approved"
            )
            if order:
                FinanceLinkageService.ensure_order_finance_record(order)
                FinanceLinkageService.ensure_receivable_for_invoice(invoice, order_id=order.id)
        elif action == "rejected":
            CustomerOrder.objects.filter(id=request.order_id).update(
                invoice_request_status="rejected"
            )

        return True, "审批成功"


class AdvancedFinanceService:
    """专业财务扩展服务类"""

    @staticmethod
    def save_with_create_time(instance):
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_bank_transaction(form) -> BankTransaction:
        with transaction.atomic():
            instance = form.save(commit=False)
            old_instance = None
            if instance.pk:
                old_instance = BankTransaction.objects.select_for_update().get(
                    pk=instance.pk
                )
                old_account_id = old_instance.account_id
                old_amount = old_instance.amount
                old_direction = old_instance.direction
            if not instance.create_time:
                instance.create_time = int(timezone.now().timestamp())
            instance.save()
            if old_instance:
                AdvancedFinanceService.apply_account_balance(
                    old_account_id,
                    old_amount,
                    old_direction,
                    reverse=True,
                )
            AdvancedFinanceService.apply_account_balance(
                instance.account_id, instance.amount, instance.direction
            )
            return instance

    @staticmethod
    def delete_bank_transaction(instance: BankTransaction) -> None:
        with transaction.atomic():
            transaction_obj = BankTransaction.objects.select_for_update().get(
                pk=instance.pk
            )
            AdvancedFinanceService.apply_account_balance(
                transaction_obj.account_id,
                transaction_obj.amount,
                transaction_obj.direction,
                reverse=True,
            )
            transaction_obj.delete()

    @staticmethod
    def apply_account_balance(
        account_id: int, amount: Decimal, direction: str, reverse=False
    ) -> None:
        account = FinanceAccount.objects.select_for_update().get(pk=account_id)
        change_amount = amount if direction == "in" else -amount
        if reverse:
            change_amount = -change_amount
        account.current_balance = (
            account.current_balance or Decimal("0")
        ) + change_amount
        account.save(update_fields=["current_balance"])

    @staticmethod
    def save_bank_reconciliation(form, user=None) -> BankReconciliation:
        instance = form.save(commit=False)
        instance.difference_amount = (instance.bank_balance or Decimal("0")) - (
            instance.book_balance or Decimal("0")
        )
        instance.status = (
            "balanced" if instance.difference_amount == Decimal("0") else "difference"
        )
        instance.reconciled_by = getattr(user, "id", 0) or 0
        instance.reconciled_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_ledger_voucher(form, user=None) -> LedgerVoucher:
        instance = form.save(commit=False)
        if instance.status == "posted" and not instance.posted_time:
            instance.posted_by = getattr(user, "id", 0) or 0
            instance.posted_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_tax_record(form) -> TaxRecord:
        instance = form.save(commit=False)
        if not instance.tax_amount and instance.taxable_amount and instance.tax_rate:
            instance.tax_amount = (
                instance.taxable_amount * instance.tax_rate / Decimal("100")
            )
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_period_close(form, user=None) -> FinancialPeriodClose:
        instance = form.save(commit=False)
        instance.profit_amount = (instance.income_amount or Decimal("0")) - (
            instance.expense_amount or Decimal("0")
        )
        if instance.status == "closed" and not instance.closed_time:
            instance.closed_by = getattr(user, "id", 0) or 0
            instance.closed_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_financial_report(form, user=None) -> FinancialReport:
        instance = form.save(commit=False)
        instance.total_equity = (instance.total_assets or Decimal("0")) - (
            instance.total_liabilities or Decimal("0")
        )
        instance.profit_amount = (instance.revenue_amount or Decimal("0")) - (
            instance.cost_amount or Decimal("0")
        )
        if instance.status in ["generated", "approved"] and not instance.generated_time:
            instance.generated_by = getattr(user, "id", 0) or 0
            instance.generated_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_expense_accrual(form, user=None) -> ExpenseAccrual:
        instance = form.save(commit=False)
        if instance.status == "accrued" and not instance.accrued_time:
            instance.accrued_by = getattr(user, "id", 0) or 0
            instance.accrued_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance


class FinanceStatisticsService:
    """财务统计服务类"""

    @staticmethod
    def get_dashboard_statistics() -> Dict:
        today = timezone.now().date()
        month_start = today.replace(day=1)
        month_start_dt = timezone.datetime.combine(month_start, timezone.datetime.min.time())
        month_start_ts = int(month_start_dt.timestamp())

        # ---- 本月统计（带月度过滤） ----
        expense_stats = ExpenseService.get_expense_statistics(start_ts=month_start_ts)
        invoice_stats = InvoiceService.get_invoice_statistics(start_ts=month_start_ts)
        income_stats = IncomeService.get_income_statistics(start_date=month_start_dt)
        payment_stats = PaymentService.get_payment_statistics(start_date=month_start_dt)

        # 本月订单财务统计
        month_order_qs = OrderFinanceRecord.objects.filter(create_time__gte=month_start_ts)
        month_order_stats = month_order_qs.aggregate(
            total_count=Count("id"),
            total_amount=Sum("total_amount"),
            paid_amount=Sum("paid_amount"),
        )
        month_order_total = month_order_stats["total_amount"] or Decimal("0")
        month_order_paid = month_order_stats["paid_amount"] or Decimal("0")

        # 本月应收统计
        month_receivable_qs = AccountsReceivable.objects.filter(create_time__gte=month_start_ts)
        month_receivable_stats = month_receivable_qs.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            received_amount=Sum("received_amount"),
        )

        # 本月应付统计
        month_payable_qs = AccountsPayable.objects.filter(create_time__gte=month_start_ts)
        month_payable_stats = month_payable_qs.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            paid_amount=Sum("paid_amount"),
        )

        # 本月银行流水统计
        month_bank_qs = BankTransaction.objects.filter(transaction_date__gte=month_start)
        month_bank_stats = month_bank_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("amount")
        )

        # 本月凭证统计
        month_voucher_qs = LedgerVoucher.objects.filter(create_time__gte=month_start_ts)
        month_voucher_stats = month_voucher_qs.aggregate(
            total_count=Count("id"),
            debit_amount=Sum("debit_amount"),
            credit_amount=Sum("credit_amount"),
        )

        # 本月税务统计
        month_tax_qs = TaxRecord.objects.filter(create_time__gte=month_start_ts)
        month_tax_stats = month_tax_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("tax_amount")
        )

        # 本月费用分配统计
        month_allocation_qs = CostAllocation.objects.filter(create_time__gte=month_start_ts)
        month_allocation_stats = month_allocation_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("total_amount")
        )

        # 本月预提统计
        month_accrual_qs = ExpenseAccrual.objects.filter(create_time__gte=month_start_ts)
        month_accrual_stats = month_accrual_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("amount")
        )

        # 本月现金流计划统计
        month_cash_flow_qs = CashFlowPlan.objects.filter(create_time__gte=month_start_ts)
        month_cash_flow_stats = month_cash_flow_qs.aggregate(
            total_count=Count("id"),
            expected_amount=Sum("expected_amount"),
            actual_amount=Sum("actual_amount"),
        )

        # 本月凭证行统计
        month_voucher_line_qs = LedgerVoucherLine.objects.filter(create_time__gte=month_start_ts)
        month_voucher_line_stats = month_voucher_line_qs.aggregate(
            total_count=Count("id"),
            debit_amount=Sum("debit_amount"),
            credit_amount=Sum("credit_amount"),
        )

        # ---- 累计统计（全量，适合账号/资产/预算等基础数据） ----
        account_stats = FinanceAccount.objects.aggregate(
            total_count=Count("id"), total_balance=Sum("current_balance")
        )
        budget_stats = FinanceBudget.objects.aggregate(
            total_count=Count("id"),
            total_amount=Sum("budget_amount"),
            used_amount=Sum("used_amount"),
        )
        asset_stats = FixedAsset.objects.aggregate(
            total_count=Count("id"),
            original_value=Sum("asset__purchase_price"),
            accumulated_depreciation=Sum("accumulated_depreciation"),
        )
        report_stats = FinancialReport.objects.aggregate(total_count=Count("id"))
        ratio_stats = FinancialRatio.objects.aggregate(total_count=Count("id"))
        subject_stats = ChartOfAccount.objects.aggregate(total_count=Count("id"))

        # ---- 计算派生值 ----
        asset_original = asset_stats["original_value"] or Decimal("0")
        asset_depreciation = asset_stats["accumulated_depreciation"] or Decimal("0")
        asset_net_value = max(asset_original - asset_depreciation, Decimal("0"))
        budget_total = budget_stats["total_amount"] or Decimal("0")
        budget_used = budget_stats["used_amount"] or Decimal("0")
        receivable_monthly_total = month_receivable_stats["total_amount"] or Decimal("0")
        receivable_monthly_received = month_receivable_stats["received_amount"] or Decimal("0")
        payable_monthly_total = month_payable_stats["total_amount"] or Decimal("0")
        payable_monthly_paid = month_payable_stats["paid_amount"] or Decimal("0")
        today_date = timezone.now().date()

        # 预算预警计数
        budget_warning_count = 0
        for budget in FinanceBudget.objects.filter(status="active"):
            if budget.usage_rate >= budget.warning_rate:
                budget_warning_count += 1

        return {
            # 统计期间信息
            "period": {
                "type": "monthly",
                "start": month_start.isoformat(),
                "end": today.isoformat(),
            },
            # 本月统计
            "expense_stats": expense_stats,
            "invoice_stats": invoice_stats,
            "income_stats": income_stats,
            "payment_stats": payment_stats,
            "order_stats": {
                "total_count": month_order_stats["total_count"] or 0,
                "total_amount": float(month_order_total),
                "paid_amount": float(month_order_paid),
                "unpaid_amount": float(
                    max(month_order_total - month_order_paid, Decimal("0"))
                ),
                "pending_count": month_order_qs.filter(payment_status="pending").count(),
                "overdue_count": month_order_qs.filter(payment_status="overdue").count(),
            },
            "receivable_stats": {
                "total_count": month_receivable_stats["total_count"] or 0,
                "total_amount": float(receivable_monthly_total),
                "received_amount": float(receivable_monthly_received),
                "remaining_amount": float(
                    max(receivable_monthly_total - receivable_monthly_received, Decimal("0"))
                ),
                "overdue_count": month_receivable_qs.filter(status="overdue").count(),
            },
            "payable_stats": {
                "total_count": month_payable_stats["total_count"] or 0,
                "total_amount": float(payable_monthly_total),
                "paid_amount": float(payable_monthly_paid),
                "remaining_amount": float(
                    max(payable_monthly_total - payable_monthly_paid, Decimal("0"))
                ),
                "overdue_count": month_payable_qs.filter(status="overdue").count(),
            },
            "bank_stats": {
                "total_count": month_bank_stats["total_count"] or 0,
                "total_amount": float(month_bank_stats["total_amount"] or Decimal("0")),
                "unmatched_count": month_bank_qs.filter(match_status="unmatched").count(),
                "difference_count": BankReconciliation.objects.filter(
                    status="difference"
                ).count(),
            },
            "voucher_stats": {
                "total_count": month_voucher_stats["total_count"] or 0,
                "debit_amount": float(month_voucher_stats["debit_amount"] or Decimal("0")),
                "credit_amount": float(month_voucher_stats["credit_amount"] or Decimal("0")),
                "draft_count": month_voucher_qs.filter(status="draft").count(),
                "posted_count": month_voucher_qs.filter(status="posted").count(),
            },
            "tax_stats": {
                "total_count": month_tax_stats["total_count"] or 0,
                "total_amount": float(month_tax_stats["total_amount"] or Decimal("0")),
                "pending_count": month_tax_qs.filter(status="draft").count(),
                "overdue_count": month_tax_qs.filter(status="overdue").count(),
            },
            "allocation_stats": {
                "total_count": month_allocation_stats["total_count"] or 0,
                "total_amount": float(month_allocation_stats["total_amount"] or Decimal("0")),
                "draft_count": month_allocation_qs.filter(status="draft").count(),
            },
            "accrual_stats": {
                "total_count": month_accrual_stats["total_count"] or 0,
                "total_amount": float(month_accrual_stats["total_amount"] or Decimal("0")),
                "draft_count": month_accrual_qs.filter(status="draft").count(),
                "accrued_count": month_accrual_qs.filter(status="accrued").count(),
            },
            "cash_flow_stats": {
                "total_count": month_cash_flow_stats["total_count"] or 0,
                "expected_amount": float(
                    month_cash_flow_stats["expected_amount"] or Decimal("0")
                ),
                "actual_amount": float(
                    month_cash_flow_stats["actual_amount"] or Decimal("0")
                ),
                "planned_count": month_cash_flow_qs.filter(status="planned").count(),
                "overdue_count": month_cash_flow_qs.filter(
                    status="planned", expected_date__lt=today_date
                ).count(),
            },
            "voucher_line_stats": {
                "total_count": month_voucher_line_stats["total_count"] or 0,
                "debit_amount": float(
                    month_voucher_line_stats["debit_amount"] or Decimal("0")
                ),
                "credit_amount": float(
                    month_voucher_line_stats["credit_amount"] or Decimal("0")
                ),
            },
            # 待处理统计（全量）
            "pending": {
                "expenses": Expense.objects.filter(
                    check_status=FinanceStatus.EXPENSE_CHECK_PENDING
                ).count(),
                "expense_payments": Expense.objects.filter(
                    check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
                    pay_status=FinanceStatus.PAY_STATUS_PENDING,
                ).count(),
                "invoices": Invoice.objects.filter(
                    open_status=FinanceStatus.INVOICE_OPEN_STATUS_NOT
                ).count(),
                "requests": InvoiceRequest.objects.filter(status="pending").count(),
            },
            # 累计统计（基础数据，适合账号/资产/预算/报表等）
            "account_stats": {
                "total_count": account_stats["total_count"] or 0,
                "active_count": FinanceAccount.objects.filter(status="active").count(),
                "total_balance": float(account_stats["total_balance"] or Decimal("0")),
            },
            "budget_stats": {
                "total_count": budget_stats["total_count"] or 0,
                "total_amount": float(budget_total),
                "used_amount": float(budget_used),
                "remaining_amount": float(
                    max(budget_total - budget_used, Decimal("0"))
                ),
                "warning_count": budget_warning_count,
            },
            "asset_stats": {
                "total_count": asset_stats["total_count"] or 0,
                "original_value": float(asset_original),
                "accumulated_depreciation": float(asset_depreciation),
                "net_value": float(asset_net_value),
                "active_count": FixedAsset.objects.filter(status="active").count(),
            },
            "period_close_stats": {
                "open_count": FinancialPeriodClose.objects.exclude(
                    status="closed"
                ).count(),
                "closed_count": FinancialPeriodClose.objects.filter(
                    status="closed"
                ).count(),
            },
            "report_stats": {
                "total_count": report_stats["total_count"] or 0,
                "draft_count": FinancialReport.objects.filter(status="draft").count(),
                "approved_count": FinancialReport.objects.filter(
                    status="approved"
                ).count(),
            },
            "ratio_stats": {
                "total_count": ratio_stats["total_count"] or 0,
                "warning_count": FinancialRatio.objects.filter(
                    status="warning"
                ).count(),
                "risk_count": FinancialRatio.objects.filter(status="risk").count(),
            },
            "subject_stats": {
                "total_count": subject_stats["total_count"] or 0,
                "active_count": ChartOfAccount.objects.filter(status="active").count(),
            },
            # 风险统计（全量）
            "risk_stats": {
                "overdue_receivables": AccountsReceivable.objects.filter(
                    due_date__lt=today_date
                )
                .exclude(status__in=["settled", "bad_debt"])
                .count(),
                "overdue_payables": AccountsPayable.objects.filter(
                    due_date__lt=today_date
                )
                .exclude(status="settled")
                .count(),
                "bank_differences": BankReconciliation.objects.filter(
                    status="difference"
                ).count(),
                "unposted_vouchers": LedgerVoucher.objects.filter(
                    status="draft"
                ).count(),
                "overdue_taxes": TaxRecord.objects.filter(status="overdue").count(),
                "open_periods": FinancialPeriodClose.objects.exclude(
                    status="closed"
                ).count(),
                "draft_reports": FinancialReport.objects.filter(status="draft").count(),
                "overdue_cash_plans": CashFlowPlan.objects.filter(
                    status="planned", expected_date__lt=today_date
                ).count(),
                "risk_ratios": FinancialRatio.objects.filter(status="risk").count(),
            },
        }

    @staticmethod
    def get_monthly_trend(months: int = 12) -> List[Dict]:
        today = timezone.now().date().replace(day=1)
        trends = []
        from dateutil.relativedelta import relativedelta

        for i in range(months - 1, -1, -1):
            month_start = today - relativedelta(months=i)
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
            start_dt = timezone.datetime.combine(month_start, timezone.datetime.min.time())
            end_dt = timezone.datetime.combine(month_end, timezone.datetime.max.time())

            start_ts = int(start_dt.timestamp())
            end_ts = int(end_dt.timestamp())

            expense_s = ExpenseService.get_expense_statistics(start_ts, end_ts)
            income_s = IncomeService.get_income_statistics(start_dt, end_dt)
            invoice_s = InvoiceService.get_invoice_statistics(start_ts, end_ts)
            payment_s = PaymentService.get_payment_statistics(start_dt, end_dt)

            # 月度订单财务统计
            month_orders = OrderFinanceRecord.objects.filter(
                create_time__gte=start_ts, create_time__lte=end_ts
            )
            order_month_total = month_orders.aggregate(
                total=Sum("total_amount"), paid=Sum("paid_amount")
            )

            # 月度应收应付统计
            month_receivable = AccountsReceivable.objects.filter(
                create_time__gte=start_ts, create_time__lte=end_ts
            ).aggregate(total=Sum("amount"), received=Sum("received_amount"))
            month_payable = AccountsPayable.objects.filter(
                create_time__gte=start_ts, create_time__lte=end_ts
            ).aggregate(total=Sum("amount"), paid=Sum("paid_amount"))

            trends.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "year_month": month_start.strftime("%Y-%m"),
                    "expense_amount": expense_s["total_amount"],
                    "expense_count": expense_s["total_count"],
                    "income_amount": income_s["total_amount"],
                    "income_count": income_s["total_count"],
                    "invoice_amount": invoice_s["total_amount"],
                    "invoice_count": invoice_s["total_count"],
                    "payment_amount": payment_s["total_amount"],
                    "payment_count": payment_s["total_count"],
                    "order_amount": float(order_month_total["total"] or Decimal("0")),
                    "order_paid": float(order_month_total["paid"] or Decimal("0")),
                    "receivable_amount": float(month_receivable["total"] or Decimal("0")),
                    "receivable_received": float(month_receivable["received"] or Decimal("0")),
                    "payable_amount": float(month_payable["total"] or Decimal("0")),
                    "payable_paid": float(month_payable["paid"] or Decimal("0")),
                }
            )

        return trends
