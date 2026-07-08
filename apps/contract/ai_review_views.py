# -*- coding: utf-8 -*-
"""AI合同审查 - API视图"""
import json
import logging
import threading

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from .models import Contract, ContractAIReview, ContractDiffRecord, ContractLegalConsultRecord
from .contract_review_service import (
    contract_review_service,
    parse_contract_file,
    compare_contracts,
    legal_consultation,
    legal_knowledge_search,
)

logger = logging.getLogger(__name__)

OCR_FOCUS_FIELD_ORDER = [
    "合同编号",
    "合同名称",
    "合同金额",
    "客户名称",
    "签约主体",
    "签订时间",
    "合同开始时间",
    "合同结束时间",
]

DISPLAY_REPORT_SECTION_TITLES = {
    "contract_info": "📄 合同信息",
    "overall_assessment": "📊 总体评估",
    "clause_reviews": "🔍 逐条审查意见",
    "review_conclusion": "📋 审查结论汇总",
}

DISPLAY_RISK_META = {
    "high": ("🔴", "高风险"),
    "medium": ("🟡", "中风险"),
    "low": ("🟢", "低风险"),
    "unknown": ("⚪", "待确认"),
}


def _safe_json_loads(raw_text, default=None):
    if default is None:
        default = {}
    if not raw_text:
        return default
    if isinstance(raw_text, (dict, list)):
        return raw_text
    try:
        return json.loads(raw_text)
    except (TypeError, ValueError):
        return default


def _serialize_legal_record(record):
    return {
        "id": record.id,
        "query_type": record.query_type,
        "query_type_label": record.get_query_type_display(),
        "question": record.question,
        "context": record.context,
        "answer": record.answer,
        "success": record.success,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M"),
        "contract_id": record.contract_id,
        "contract_name": record.contract.name if record.contract_id else "",
    }


def _build_contract_system_data(contract):
    from apps.common.utils import timestamp_to_date

    return {
        "合同编号": contract.code or "",
        "合同名称": contract.name or "",
        "合同金额": f"{contract.cost}元" if contract.cost else "",
        "客户名称": contract.customer or "",
        "签约主体": contract.subject_id or "",
        "合同开始时间": timestamp_to_date(contract.start_time, "%Y-%m-%d") if contract.start_time else "",
        "合同结束时间": timestamp_to_date(contract.end_time, "%Y-%m-%d") if contract.end_time else "",
        "签订时间": timestamp_to_date(contract.sign_time, "%Y-%m-%d") if contract.sign_time else "",
    }


def _build_focus_review_fields(contract, contract_text):
    text = str(contract_text or "").strip()
    if not text:
        return []

    if contract:
        items = contract_review_service.cross_reference_check(
            contract_text=text,
            system_data=_build_contract_system_data(contract),
        )
        item_map = {item.get("field"): item for item in items}
        return [item_map[field] for field in OCR_FOCUS_FIELD_ORDER if field in item_map]

    extracted = contract_review_service._extract_contract_structured_fields(text)
    extracted_field_map = {
        "合同编号": "合同编号",
        "合同名称": "合同名称",
        "合同金额": "合同金额",
        "客户名称": "签约对方名称",
        "签约主体": "我方签约主体名称",
        "签订时间": "签订时间",
        "合同开始时间": "合同开始日期",
        "合同结束时间": "合同结束日期",
    }
    results = []
    for field in OCR_FOCUS_FIELD_ORDER:
        extracted_value = extracted.get(extracted_field_map.get(field, field), "")
        results.append(
            contract_review_service._build_cross_check_item(
                field=field,
                extracted_value=extracted_value,
                system_value="",
            )
        )
    return results


def _build_review_overall_assessment(review):
    return {
        "risk_level": review.overall_risk_level,
        "summary": review.overall_summary,
        "final_recommendation": review.final_recommendation,
    }


def _first_non_empty(*values):
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _format_risk_display(risk_level, spaced=False):
    emoji, label = DISPLAY_RISK_META.get(risk_level or "unknown", DISPLAY_RISK_META["unknown"])
    connector = " " if spaced else ""
    return f"{emoji}{connector}{label}"


def _build_contract_info_items(contract_info):
    contract_info = contract_info or {}
    contract_name = str(contract_info.get("contract_name") or "").strip()
    contract_type = str(contract_info.get("contract_type") or "").strip()
    if contract_name and contract_type and contract_type not in contract_name:
        contract_name = f"{contract_name} / {contract_type}"
    contract_name = contract_name or contract_type or "待确认"
    our_role = _first_non_empty(contract_info.get("our_role"), "待确认")
    core_demands = _first_non_empty(
        contract_info.get("core_demands"),
        "确保合同条款合法合规，并结合业务事实进一步复核后再签署。",
    )
    return [
        {"label": "合同名称/类型", "value": contract_name},
        {"label": "我方签约角色", "value": our_role},
        {"label": "核心诉求", "value": core_demands},
    ]


def _build_display_report(contract_info, overall_assessment, clause_reviews=None, review_conclusion=None, final_recommendation=""):
    overall_assessment = overall_assessment or {}
    clause_reviews = clause_reviews or []
    review_conclusion = review_conclusion or []
    final_recommendation = _first_non_empty(
        final_recommendation,
        overall_assessment.get("final_recommendation"),
        "建议结合合同原文及事实背景补充复核后再签署。",
    )

    display_clauses = []
    for clause in clause_reviews:
        clause_no = str(clause.get("clause_no") or "").strip() or "待确认条款"
        title = str(clause.get("title") or "").strip()
        heading = clause_no if not title else f"{clause_no} [{title}]"
        display_clauses.append({
            "heading": heading,
            "clause_no": clause_no,
            "title": title,
            "original_summary": clause.get("original_summary", ""),
            "risk_analysis": clause.get("risk_analysis", ""),
            "risk_level": clause.get("risk_level", "unknown"),
            "risk_display": _format_risk_display(clause.get("risk_level", "unknown")),
            "suggestion": clause.get("suggestion", ""),
        })

    conclusion_rows = []
    for item in review_conclusion:
        conclusion_rows.append({
            "clause_no": item.get("clause_no", ""),
            "title": item.get("title", ""),
            "risk_level": item.get("risk_level", "unknown"),
            "risk_display": _format_risk_display(item.get("risk_level", "unknown"), spaced=True),
            "action": item.get("action", ""),
        })

    return {
        "section_titles": DISPLAY_REPORT_SECTION_TITLES,
        "contract_info": _build_contract_info_items(contract_info),
        "overall_assessment": {
            "summary": overall_assessment.get("summary", ""),
            "risk_level": overall_assessment.get("risk_level", "unknown"),
            "risk_display": _format_risk_display(overall_assessment.get("risk_level", "unknown")),
            "final_recommendation": final_recommendation,
        },
        "clause_reviews": display_clauses,
        "review_conclusion": {
            "rows": conclusion_rows,
            "final_recommendation": final_recommendation,
        },
    }


def _summarize_focus_review_fields(fields):
    fields = fields or []
    summary = {
        "total_count": len(fields),
        "matched_count": 0,
        "attention_count": 0,
        "missing_count": 0,
    }
    for item in fields:
        if item.get("match"):
            summary["matched_count"] += 1
            continue
        status = str(item.get("status", ""))
        if "未" in status:
            summary["missing_count"] += 1
        else:
            summary["attention_count"] += 1
    return summary


def _extract_focus_review_fields_from_review(review):
    raw_payload = _safe_json_loads(review.raw_response, default={})
    if isinstance(raw_payload, dict):
        fields = raw_payload.get("focus_review_fields", [])
        if isinstance(fields, list):
            return fields
    return []


def _extract_quick_review_result(review):
    raw_payload = _safe_json_loads(review.raw_response, default={})
    if isinstance(raw_payload, dict) and isinstance(raw_payload.get("analysis"), dict):
        raw_payload = raw_payload["analysis"]

    key_risks = raw_payload.get("key_risks", []) if isinstance(raw_payload, dict) else []
    if not isinstance(key_risks, list):
        key_risks = []

    return {
        "risk_level": review.overall_risk_level or (raw_payload.get("risk_level", "unknown") if isinstance(raw_payload, dict) else "unknown"),
        "brief_summary": review.overall_summary or (raw_payload.get("brief_summary", "") if isinstance(raw_payload, dict) else ""),
        "key_risks": key_risks,
    }


def _serialize_review_summary(review):
    raw_payload = _safe_json_loads(review.raw_response, default={})
    task_status = raw_payload.get("task_status", "completed") if isinstance(raw_payload, dict) else "completed"
    return {
        "id": review.id,
        "review_version": review.review_version,
        "review_type": review.review_type,
        "review_type_label": review.get_review_type_display(),
        "overall_risk_level": review.overall_risk_level,
        "overall_summary": review.overall_summary,
        "reviewed_at": review.reviewed_at.strftime("%Y-%m-%d %H:%M"),
        "is_latest": review.is_latest,
        "task_status": task_status,
        "task_error": raw_payload.get("task_error", "") if isinstance(raw_payload, dict) else "",
    }


def _serialize_review_detail(review):
    focus_review_fields = _extract_focus_review_fields_from_review(review)
    raw_payload = _safe_json_loads(review.raw_response, default={})
    task_status = raw_payload.get("task_status", "completed") if isinstance(raw_payload, dict) else "completed"
    overall_assessment = _build_review_overall_assessment(review)
    payload = {
        "review_id": review.id,
        "contract_id": review.contract_id,
        "review_version": review.review_version,
        "review_type": review.review_type,
        "review_type_label": review.get_review_type_display(),
        "contract_info": review.contract_info,
        "overall_risk_level": review.overall_risk_level,
        "overall_summary": review.overall_summary,
        "overall_assessment": overall_assessment,
        "clause_reviews": review.clause_reviews,
        "review_conclusion": review.review_conclusion,
        "final_recommendation": review.final_recommendation,
        "data_cross_check": review.data_cross_check,
        "focus_review_fields": focus_review_fields,
        "focus_review_summary": _summarize_focus_review_fields(focus_review_fields),
        "reviewed_at": review.reviewed_at.strftime("%Y-%m-%d %H:%M"),
        "is_latest": review.is_latest,
        "status": task_status,
        "pending": task_status in {"queued", "running"},
        "failed": task_status == "failed",
        "task_error": raw_payload.get("task_error", "") if isinstance(raw_payload, dict) else "",
    }
    payload["display_report"] = _build_display_report(
        review.contract_info,
        overall_assessment,
        review.clause_reviews,
        review.review_conclusion,
        review.final_recommendation,
    )
    if review.review_type == "quick":
        payload["quick_review_result"] = _extract_quick_review_result(review)
    return payload


def _create_contract_review_record(contract, review_type, result, reviewed_by=None, contract_info=None, data_cross_check=None):
    ContractAIReview.objects.filter(contract=contract, is_latest=True).update(is_latest=False)
    review_count = ContractAIReview.objects.filter(contract=contract).count()
    contract_info = contract_info or result.get("contract_info", {})
    data_cross_check = data_cross_check or []

    if review_type == "quick":
        overall_risk_level = result.get("risk_level", "unknown")
        overall_summary = result.get("brief_summary", "")
        clause_reviews = []
        review_conclusion = []
        final_recommendation = "建议结合完整审查结果进一步确认逐条修改方案。"
    else:
        overall_assessment = result.get("overall_assessment", {})
        overall_risk_level = overall_assessment.get("risk_level", "unknown")
        overall_summary = overall_assessment.get("summary", "")
        clause_reviews = result.get("clause_reviews", [])
        review_conclusion = result.get("review_conclusion", [])
        final_recommendation = overall_assessment.get("final_recommendation", "")

    return ContractAIReview.objects.create(
        contract=contract,
        review_version=review_count + 1,
        review_type=review_type,
        contract_info=contract_info,
        overall_risk_level=overall_risk_level,
        overall_summary=overall_summary,
        clause_reviews=clause_reviews,
        review_conclusion=review_conclusion,
        final_recommendation=final_recommendation,
        data_cross_check=data_cross_check,
        reviewed_by=reviewed_by,
        raw_response=json.dumps(result, ensure_ascii=False),
    )


def _create_pending_full_review_record(contract, contract_info=None, data_cross_check=None, focus_review_fields=None):
    ContractAIReview.objects.filter(contract=contract, is_latest=True).update(is_latest=False)
    review_count = ContractAIReview.objects.filter(contract=contract).count()
    payload = {
        "task_status": "queued",
        "focus_review_fields": focus_review_fields or [],
    }
    return ContractAIReview.objects.create(
        contract=contract,
        review_version=review_count + 1,
        review_type="full",
        contract_info=contract_info or {},
        overall_risk_level="unknown",
        overall_summary="AI正在生成逐条审查意见，请稍候刷新查看。",
        clause_reviews=[],
        review_conclusion=[],
        final_recommendation="",
        data_cross_check=data_cross_check or [],
        raw_response=json.dumps(payload, ensure_ascii=False),
        is_latest=True,
    )


def _update_review_task_status(review, status, result_payload=None):
    payload = _safe_json_loads(review.raw_response, default={})
    if not isinstance(payload, dict):
        payload = {}
    payload["task_status"] = status
    if result_payload:
        payload.update(result_payload)
    review.raw_response = json.dumps(payload, ensure_ascii=False)
    review.save(update_fields=["raw_response", "update_time"] if hasattr(review, "update_time") else ["raw_response"])


def _run_contract_full_review_job(review_id, contract_id, contract_text, contract_name, our_role, core_demands, extra_context, reviewed_by_id=None):
    try:
        review = ContractAIReview.objects.get(id=review_id)
        contract = Contract.objects.get(id=contract_id, delete_time=0)
        _update_review_task_status(review, "running")

        result = contract_review_service.review_contract(
            contract_text=contract_text,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
            extra_context=extra_context,
        )
        data_cross_check = contract_review_service.cross_reference_check(
            contract_text=contract_text,
            system_data=_build_contract_system_data(contract),
        )
        focus_review_fields = _build_focus_review_fields(contract, contract_text)
        result["focus_review_fields"] = focus_review_fields
        result["focus_review_summary"] = _summarize_focus_review_fields(focus_review_fields)
        result["task_status"] = "completed"

        overall_assessment = result.get("overall_assessment", {})
        review.contract_info = result.get("contract_info", {})
        review.overall_risk_level = overall_assessment.get("risk_level", "unknown")
        review.overall_summary = overall_assessment.get("summary", "")
        review.clause_reviews = result.get("clause_reviews", [])
        review.review_conclusion = result.get("review_conclusion", [])
        review.final_recommendation = overall_assessment.get("final_recommendation", "")
        review.data_cross_check = data_cross_check
        review.raw_response = json.dumps(result, ensure_ascii=False)
        review.save(update_fields=[
            "contract_info",
            "overall_risk_level",
            "overall_summary",
            "clause_reviews",
            "review_conclusion",
            "final_recommendation",
            "data_cross_check",
            "raw_response",
        ])

        contract.ai_risk_level = review.overall_risk_level
        high_risks = [c for c in review.clause_reviews if c.get("risk_level") == "high"]
        contract.ai_risk_points = [{"clause": c.get("clause_no", ""), "title": c.get("title", ""), "risk": c.get("risk_analysis", "")} for c in high_risks]
        contract.ai_key_terms = [c.get("title", "") for c in review.clause_reviews]
        contract.save(update_fields=["ai_risk_level", "ai_risk_points", "ai_key_terms"])
    except Exception as exc:
        logger.error("后台执行AI合同完整审查失败(review_id=%s): %s", review_id, exc, exc_info=True)
        try:
            review = ContractAIReview.objects.get(id=review_id)
            payload = _safe_json_loads(review.raw_response, default={})
            if not isinstance(payload, dict):
                payload = {}
            payload["task_status"] = "failed"
            payload["task_error"] = str(exc)
            review.raw_response = json.dumps(payload, ensure_ascii=False)
            review.overall_summary = "详细审查生成失败，请重试。"
            review.save(update_fields=["raw_response", "overall_summary"])
        except Exception:
            logger.exception("更新AI合同审查失败状态时再次出错(review_id=%s)", review_id)


def _start_contract_full_review_job(review_id, contract_id, contract_text, contract_name, our_role, core_demands, extra_context, reviewed_by_id=None):
    thread = threading.Thread(
        target=_run_contract_full_review_job,
        args=(review_id, contract_id, contract_text, contract_name, our_role, core_demands, extra_context, reviewed_by_id),
        daemon=True,
    )
    thread.start()
    return thread


def _load_contract_text_from_attachment(contract):
    """优先从合同已有附件中解析文本，并回填到合同内容字段。"""
    fallback_content = (contract.content or "").strip()
    fallback_remark = (contract.remark or "").strip()
    result = {
        "contract_text": fallback_content or fallback_remark,
        "attachment_used": False,
        "attachment_name": contract.scan_file_name,
        "attachment_error": "",
        "attachment_ocr_used": False,
        "attachment_parse_method": "",
        "attachment_accuracy_notice": "",
        "focus_review_fields": [],
    }

    if not contract.scan_file:
        return result

    if fallback_content:
        result["contract_text"] = fallback_content
        result["attachment_used"] = True
        result["focus_review_fields"] = _build_focus_review_fields(contract, fallback_content)
        return result

    try:
        contract.scan_file.open("rb")
        contract.scan_file.seek(0)
        parsed = parse_contract_file(contract.scan_file, include_meta=True)
    except Exception as exc:
        logger.warning("解析合同已有附件失败(contract_id=%s): %s", contract.id, exc)
        result["attachment_error"] = str(exc)
        if fallback_content:
            result["contract_text"] = fallback_content
        elif fallback_remark:
            result["contract_text"] = fallback_remark
        return result
    finally:
        try:
            contract.scan_file.close()
        except Exception:
            pass

    parsed_text = (parsed.get("text") or "").strip()
    result["attachment_ocr_used"] = bool(parsed.get("ocr_used"))
    result["attachment_parse_method"] = parsed.get("parse_method", "") or ""
    result["attachment_accuracy_notice"] = parsed.get("accuracy_notice", "") or ""

    if parsed_text:
        if contract.content != parsed_text:
            contract.content = parsed_text
            contract.save(update_fields=["content", "update_time"])
        result["contract_text"] = parsed_text
        result["attachment_used"] = True
        result["focus_review_fields"] = _build_focus_review_fields(contract, parsed_text)
    elif fallback_remark:
        result["contract_text"] = fallback_remark

    return result


# ── 合同审查 ─────────────────────────────────────

@login_required
def ai_contract_review_api(request, contract_id):
    """AI合同逐条审查 - 启动后台审查任务并立即返回状态"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        contract = get_object_or_404(Contract, id=contract_id, delete_time=0)

        # 获取合同文本：优先使用上传文件解析，其次使用content字段
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        contract_text = body.get("contract_text", "")
        extra_context = body.get("extra_context", "")
        contract_name = body.get("contract_name", contract.name or "")
        our_role = body.get("our_role", "")
        core_demands = body.get("core_demands", "")

        if not contract_text:
            contract_text = contract.content or contract.remark or ""
        if not contract_text.strip():
            return JsonResponse({"code": 400, "msg": "合同文本为空，请先上传合同文件或填写合同内容"})

        data_cross_check = contract_review_service.cross_reference_check(
            contract_text=contract_text,
            system_data=_build_contract_system_data(contract),
        )
        focus_review_fields = _build_focus_review_fields(contract, contract_text)
        review = _create_pending_full_review_record(
            contract=contract,
            contract_info={
                "contract_name": contract_name or contract.name or "",
                "our_role": our_role,
                "core_demands": core_demands,
            },
            data_cross_check=data_cross_check,
            focus_review_fields=focus_review_fields,
        )
        _start_contract_full_review_job(
            review_id=review.id,
            contract_id=contract.id,
            contract_text=contract_text,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
            extra_context=extra_context,
            reviewed_by_id=getattr(request.user, "id", None),
        )

        return JsonResponse({
            "code": 0,
            "msg": "审查任务已启动",
            "data": {
                "review_id": review.id,
                "contract_id": contract.id,
                "status": "queued",
                "pending": True,
                "overall_summary": review.overall_summary,
            }
        })
    except Exception as e:
        logger.error(f"AI合同审查失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": f"审查失败: {str(e)}"}, status=500)


@login_required
def ai_contract_review_preview_api(request, contract_id):
    """AI合同审查预评估 - 快速返回首屏风险结论，不落历史记录"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        contract = get_object_or_404(Contract, id=contract_id, delete_time=0)
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        contract_text = body.get("contract_text", "")
        contract_name = body.get("contract_name", contract.name or "")
        our_role = body.get("our_role", "")
        core_demands = body.get("core_demands", "")

        if not contract_text:
            contract_text = contract.content or contract.remark or ""
        if not contract_text.strip():
            return JsonResponse({"code": 400, "msg": "合同文本为空，请先上传合同文件或填写合同内容"})

        quick_result = contract_review_service.quick_review(contract_text)
        data_cross_check = contract_review_service.cross_reference_check(
            contract_text=contract_text,
            system_data=_build_contract_system_data(contract),
        )
        focus_review_fields = _build_focus_review_fields(contract, contract_text)

        overall_summary = quick_result.get("brief_summary", "")
        overall_risk_level = quick_result.get("risk_level", "unknown")
        overall_assessment = {
            "risk_level": overall_risk_level,
            "summary": overall_summary or "已完成预评估，建议先核对关键字段与高风险提示，再继续逐条审查。",
            "final_recommendation": "已生成预评估结果，详细修改建议正在准备中。",
        }
        contract_info = {
            "contract_name": contract_name or contract.name or "",
            "our_role": our_role,
            "core_demands": core_demands,
        }

        return JsonResponse({
            "code": 0,
            "msg": "预评估完成",
            "data": {
                "contract_id": contract.id,
                "contract_info": contract_info,
                "quick_review_result": quick_result,
                "overall_assessment": overall_assessment,
                "display_report": _build_display_report(contract_info, overall_assessment),
                "data_cross_check": data_cross_check,
                "focus_review_fields": focus_review_fields,
                "focus_review_summary": _summarize_focus_review_fields(focus_review_fields),
                "pending_full_review": True,
            }
        })
    except Exception as e:
        logger.error(f"AI合同预评估失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": f"预评估失败: {str(e)}"}, status=500)


@login_required
def ai_contract_review_history_api(request, contract_id):
    """获取合同审查历史"""
    reviews = ContractAIReview.objects.filter(contract_id=contract_id).order_by("-reviewed_at", "-id")
    return JsonResponse({
        "code": 0,
        "data": [_serialize_review_summary(review) for review in reviews],
    })


@login_required
def ai_contract_review_detail_api(request, review_id):
    """获取单次审查详情"""
    review = get_object_or_404(ContractAIReview, id=review_id)
    return JsonResponse({
        "code": 0,
        "data": _serialize_review_detail(review)
    })


@login_required
def ai_contract_review_status_api(request, review_id):
    """获取完整审查任务状态"""
    review = get_object_or_404(ContractAIReview, id=review_id)
    raw_payload = _safe_json_loads(review.raw_response, default={})
    status = raw_payload.get("task_status", "completed") if isinstance(raw_payload, dict) else "completed"
    return JsonResponse({
        "code": 0,
        "data": {
            "review_id": review.id,
            "contract_id": review.contract_id,
            "status": status,
            "pending": status in {"queued", "running"},
            "failed": status == "failed",
            "detail_ready": status == "completed",
            "overall_summary": review.overall_summary,
            "task_error": raw_payload.get("task_error", "") if isinstance(raw_payload, dict) else "",
        }
    })


# ── 文件上传解析 ──────────────────────────────────

@login_required
@csrf_exempt
def ai_contract_file_parse_api(request):
    """上传合同文件并解析为文本"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        uploaded = request.FILES.get("file")
        contract_id = request.POST.get("contract_id", "")
        contract = None

        if not uploaded:
            return JsonResponse({"code": 400, "msg": "请选择要上传的合同文件"})

        parsed = parse_contract_file(uploaded, include_meta=True)
        text = parsed["text"]

        # 如果提供了contract_id，更新合同扫描件和内容
        if contract_id:
            try:
                contract = Contract.objects.get(id=int(contract_id), delete_time=0)
                contract.scan_file = uploaded
                contract.content = text
                contract.save(update_fields=["scan_file", "content"])
            except Contract.DoesNotExist:
                contract = None

        focus_review_fields = _build_focus_review_fields(contract, text)

        return JsonResponse({
            "code": 0,
            "msg": "文件解析成功",
            "data": {
                "file_name": uploaded.name,
                "text_length": len(text),
                "text_preview": text[:500],
                "full_text": text,
                "ocr_used": parsed.get("ocr_used", False),
                "parse_method": parsed.get("parse_method", ""),
                "accuracy_notice": parsed.get("accuracy_notice", ""),
                "focus_review_fields": focus_review_fields,
                "focus_review_summary": _summarize_focus_review_fields(focus_review_fields),
            }
        })
    except ValueError as e:
        return JsonResponse({"code": 400, "msg": str(e)})
    except Exception as e:
        logger.error(f"文件解析失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": f"文件解析失败: {str(e)}"}, status=500)


# ── 差异比对 ─────────────────────────────────────

@login_required
def ai_contract_diff_api(request, contract_id):
    """合同差异比对"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        contract = get_object_or_404(Contract, id=contract_id, delete_time=0)

        # 获取原始文本
        original_text = contract.content or contract.remark or ""

        # 获取对比文本：上传文件或直接传入
        compare_text = ""
        uploaded = request.FILES.get("file")
        if uploaded:
            compare_text = parse_contract_file(uploaded)
            # 保存对比文件
            record = ContractDiffRecord.objects.create(
                contract=contract,
                compare_file=uploaded,
                original_text=original_text,
                compare_text=compare_text,
                compared_by=request.user,
            )
        else:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
            compare_text = body.get("compare_text", "")
            if not compare_text:
                return JsonResponse({"code": 400, "msg": "请上传对比文件或输入对比文本"})
            record = ContractDiffRecord.objects.create(
                contract=contract,
                original_text=original_text,
                compare_text=compare_text,
                compared_by=request.user,
            )

        if not original_text.strip():
            return JsonResponse({"code": 400, "msg": "合同原文为空，无法进行差异比对"})

        # 执行差异对比
        diff_result = compare_contracts(original_text, compare_text)

        # 更新记录
        record.diff_result = diff_result.get("diff_blocks", [])
        record.risk_flags = diff_result.get("risk_flags", [])
        record.save(update_fields=["diff_result", "risk_flags"])

        return JsonResponse({
            "code": 0,
            "msg": "比对完成",
            "data": {
                "record_id": record.id,
                "total_diffs": diff_result["total_diffs"],
                "risk_count": diff_result["risk_count"],
                "diff_blocks": diff_result["diff_blocks"][:50],  # 限制返回前50条
                "risk_flags": diff_result["risk_flags"],
                "summary": diff_result["summary"],
            }
        })
    except Exception as e:
        logger.error(f"差异比对失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": f"比对失败: {str(e)}"}, status=500)


# ── 法律咨询 ─────────────────────────────────────

@login_required
def ai_legal_consultation_api(request):
    """智能法律咨询"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        question = body.get("question", "").strip()
        context = body.get("context", "").strip()
        contract_id = body.get("contract_id")

        if not question:
            return JsonResponse({"code": 400, "msg": "请输入法律问题"})

        result = legal_consultation(question, context)
        contract = None
        if contract_id:
            try:
                contract = Contract.objects.get(id=int(contract_id), delete_time=0)
            except (Contract.DoesNotExist, TypeError, ValueError):
                contract = None

        record = ContractLegalConsultRecord.objects.create(
            user=request.user,
            contract=contract,
            query_type="consultation",
            question=question,
            context=context,
            answer=result.get("answer", ""),
            success=result.get("success", False),
        )
        return JsonResponse({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"法律咨询失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": str(e)}, status=500)


@login_required
def ai_legal_knowledge_api(request):
    """法律法规知识查询"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        query = body.get("query", "").strip()
        contract_id = body.get("contract_id")

        if not query:
            return JsonResponse({"code": 400, "msg": "请输入查询关键词"})

        result = legal_knowledge_search(query)
        contract = None
        if contract_id:
            try:
                contract = Contract.objects.get(id=int(contract_id), delete_time=0)
            except (Contract.DoesNotExist, TypeError, ValueError):
                contract = None

        answer = result.get("results", "")
        if not answer and result.get("answer"):
            answer = result.get("answer", "")

        ContractLegalConsultRecord.objects.create(
            user=request.user,
            contract=contract,
            query_type="knowledge",
            question=query,
            answer=answer,
            success=result.get("success", False),
        )
        return JsonResponse({"code": 0, "data": result})
    except Exception as e:
        logger.error(f"法律知识查询失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": str(e)}, status=500)


@login_required
def ai_legal_consultation_history_api(request):
    """获取当前用户的法律咨询历史记录"""
    limit = request.GET.get("limit", "20")
    query_type = request.GET.get("query_type", "").strip()

    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20

    records = ContractLegalConsultRecord.objects.filter(user=request.user)
    if query_type in {"consultation", "knowledge"}:
        records = records.filter(query_type=query_type)

    data = [_serialize_legal_record(record) for record in records[:limit]]
    return JsonResponse({"code": 0, "data": data})


# ── 快速审查 ─────────────────────────────────────

@login_required
def ai_contract_quick_review_api(request):
    """合同快速审查 - 仅返回风险评级"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        contract_text = body.get("contract_text", "").strip()
        contract_id = body.get("contract_id")
        contract_name = body.get("contract_name", "").strip()
        our_role = body.get("our_role", "").strip()
        core_demands = body.get("core_demands", "").strip()

        if not contract_text:
            return JsonResponse({"code": 400, "msg": "请提供合同文本"})

        result = contract_review_service.quick_review(contract_text)
        focus_review_fields = []
        review = None
        if contract_id:
            try:
                contract = Contract.objects.get(id=int(contract_id), delete_time=0)
                focus_review_fields = _build_focus_review_fields(contract, contract_text)
                result["focus_review_fields"] = focus_review_fields
                result["focus_review_summary"] = _summarize_focus_review_fields(focus_review_fields)
                review = _create_contract_review_record(
                    contract=contract,
                    review_type="quick",
                    result=result,
                    reviewed_by=request.user,
                    contract_info={
                        "contract_name": contract_name or contract.name or "",
                        "our_role": our_role,
                        "core_demands": core_demands,
                    },
                )
                contract.ai_risk_level = result.get("risk_level", "unknown")
                contract.ai_risk_points = [
                    {
                        "clause": "快速评估",
                        "title": f"风险点{i + 1}",
                        "risk": risk,
                    }
                    for i, risk in enumerate(result.get("key_risks", [])[:5])
                ]
                contract.save(update_fields=["ai_risk_level", "ai_risk_points"])
            except (Contract.DoesNotExist, TypeError, ValueError):
                review = None

        payload = dict(result)
        if focus_review_fields and "focus_review_fields" not in payload:
            payload["focus_review_fields"] = focus_review_fields
            payload["focus_review_summary"] = _summarize_focus_review_fields(focus_review_fields)
        if review:
            payload["review_id"] = review.id
            payload["review_type"] = review.review_type
            payload["review_type_label"] = review.get_review_type_display()
            payload["reviewed_at"] = review.reviewed_at.strftime("%Y-%m-%d %H:%M")
        return JsonResponse({"code": 0, "data": payload})
    except Exception as e:
        logger.error(f"快速审查失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": str(e)}, status=500)

# ── 页面视图 ─────────────────────────────────────

from django.shortcuts import render

@login_required
def ai_review_page(request, contract_id):
    """AI合同审查页面"""
    contract = get_object_or_404(Contract, id=contract_id, delete_time=0)
    latest_review = ContractAIReview.objects.filter(
        contract=contract, is_latest=True
    ).first()
    attachment_info = _load_contract_text_from_attachment(contract)
    contract_info = latest_review.contract_info if latest_review else {}

    our_role_default = contract_info.get("our_role", "")
    if not our_role_default and contract.subject_id:
        our_role_default = f"甲方 - {contract.subject_id}"

    core_demands_default = contract_info.get("core_demands", "")
    if not core_demands_default:
        core_demands_default = "确保合同条款合法合规，重点关注付款、履约、违约责任和争议解决风险"

    context = {
        "contract": contract,
        "latest_review": latest_review,
        "contract_text": attachment_info["contract_text"],
        "attachment_used": attachment_info["attachment_used"],
        "attachment_name": attachment_info["attachment_name"],
        "attachment_error": attachment_info["attachment_error"],
        "attachment_ocr_used": attachment_info["attachment_ocr_used"],
        "attachment_parse_method": attachment_info["attachment_parse_method"],
        "attachment_accuracy_notice": attachment_info["attachment_accuracy_notice"],
        "attachment_focus_review_fields_json": json.dumps(attachment_info["focus_review_fields"], ensure_ascii=False),
        "our_role_default": our_role_default,
        "core_demands_default": core_demands_default,
    }
    return render(request, "contract/ai_review.html", context)


@login_required
def ai_review_list_page(request):
    """AI合同审查 - 合同选择列表页面"""
    return render(request, "contract/ai_review_list.html")


@login_required
def ai_review_history_page(request, contract_id):
    """AI合同审查记录页 - 右侧弹出查看历史"""
    contract = get_object_or_404(Contract, id=contract_id, delete_time=0)
    latest_review = ContractAIReview.objects.filter(contract=contract, is_latest=True).first()
    context = {
        "contract": contract,
        "latest_review": latest_review,
    }
    return render(request, "contract/ai_review_history.html", context)
