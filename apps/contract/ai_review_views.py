# -*- coding: utf-8 -*-
"""AI合同审查 - API视图"""
import json
import logging

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


def _build_review_overall_assessment(review):
    return {
        "risk_level": review.overall_risk_level,
        "summary": review.overall_summary,
        "final_recommendation": review.final_recommendation,
    }


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
    return {
        "id": review.id,
        "review_version": review.review_version,
        "review_type": review.review_type,
        "review_type_label": review.get_review_type_display(),
        "overall_risk_level": review.overall_risk_level,
        "overall_summary": review.overall_summary,
        "reviewed_at": review.reviewed_at.strftime("%Y-%m-%d %H:%M"),
        "is_latest": review.is_latest,
    }


def _serialize_review_detail(review):
    payload = {
        "review_id": review.id,
        "contract_id": review.contract_id,
        "review_version": review.review_version,
        "review_type": review.review_type,
        "review_type_label": review.get_review_type_display(),
        "contract_info": review.contract_info,
        "overall_risk_level": review.overall_risk_level,
        "overall_summary": review.overall_summary,
        "overall_assessment": _build_review_overall_assessment(review),
        "clause_reviews": review.clause_reviews,
        "review_conclusion": review.review_conclusion,
        "final_recommendation": review.final_recommendation,
        "data_cross_check": review.data_cross_check,
        "reviewed_at": review.reviewed_at.strftime("%Y-%m-%d %H:%M"),
        "is_latest": review.is_latest,
    }
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


def _load_contract_text_from_attachment(contract):
    """优先从合同已有附件中解析文本，并回填到合同内容字段。"""
    fallback_content = (contract.content or "").strip()
    fallback_remark = (contract.remark or "").strip()
    result = {
        "contract_text": fallback_content or fallback_remark,
        "attachment_used": False,
        "attachment_name": contract.scan_file_name,
        "attachment_error": "",
    }

    if not contract.scan_file:
        return result

    if fallback_content:
        result["contract_text"] = fallback_content
        result["attachment_used"] = True
        return result

    try:
        contract.scan_file.open("rb")
        contract.scan_file.seek(0)
        parsed_text = parse_contract_file(contract.scan_file)
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

    parsed_text = parsed_text.strip()
    if parsed_text:
        if contract.content != parsed_text:
            contract.content = parsed_text
            contract.save(update_fields=["content", "update_time"])
        result["contract_text"] = parsed_text
        result["attachment_used"] = True
    elif fallback_remark:
        result["contract_text"] = fallback_remark

    return result


# ── 合同审查 ─────────────────────────────────────

@login_required
def ai_contract_review_api(request, contract_id):
    """AI合同逐条审查 - 主审查接口"""
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

        # 构建系统录入数据用于交叉校验
        from apps.common.utils import timestamp_to_date
        system_data = {
            "合同编号": contract.code or "",
            "合同名称": contract.name or "",
            "合同金额": f"{contract.cost}元" if contract.cost else "",
            "客户名称": contract.customer or "",
            "签约主体": contract.subject_id or "",
            "合同开始时间": timestamp_to_date(contract.start_time, "%Y-%m-%d") if contract.start_time else "",
            "合同结束时间": timestamp_to_date(contract.end_time, "%Y-%m-%d") if contract.end_time else "",
            "签订时间": timestamp_to_date(contract.sign_time, "%Y-%m-%d") if contract.sign_time else "",
        }

        # 调用AI审查（主审查）
        result = contract_review_service.review_contract(
            contract_text=contract_text,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
            extra_context=extra_context,
        )

        # 交叉校验：合同原文 vs 系统录入数据
        data_cross_check = contract_review_service.cross_reference_check(
            contract_text=contract_text,
            system_data=system_data,
        )

        # 保存审查结果
        review = _create_contract_review_record(
            contract=contract,
            review_type="full",
            result=result,
            reviewed_by=request.user,
            contract_info=result.get("contract_info", {}),
            data_cross_check=data_cross_check,
        )

        # 同步更新Contract模型的风险字段
        contract.ai_risk_level = result.get("overall_assessment", {}).get("risk_level", "unknown")
        high_risks = [c for c in result.get("clause_reviews", []) if c.get("risk_level") == "high"]
        contract.ai_risk_points = [{"clause": c.get("clause_no", ""), "title": c.get("title", ""),
                                    "risk": c.get("risk_analysis", "")} for c in high_risks]
        contract.ai_key_terms = [c.get("title", "") for c in result.get("clause_reviews", [])]
        contract.save(update_fields=["ai_risk_level", "ai_risk_points", "ai_key_terms"])

        return JsonResponse({
            "code": 0,
            "msg": "审查完成",
            "data": {
                **_serialize_review_detail(review),
            }
        })
    except Exception as e:
        logger.error(f"AI合同审查失败: {e}", exc_info=True)
        return JsonResponse({"code": 500, "msg": f"审查失败: {str(e)}"}, status=500)


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

        if not uploaded:
            return JsonResponse({"code": 400, "msg": "请选择要上传的合同文件"})

        text = parse_contract_file(uploaded)

        # 如果提供了contract_id，更新合同扫描件和内容
        if contract_id:
            try:
                contract = Contract.objects.get(id=int(contract_id), delete_time=0)
                contract.scan_file = uploaded
                contract.content = text
                contract.save(update_fields=["scan_file", "content"])
            except Contract.DoesNotExist:
                pass

        return JsonResponse({
            "code": 0,
            "msg": "文件解析成功",
            "data": {
                "file_name": uploaded.name,
                "text_length": len(text),
                "text_preview": text[:500],
                "full_text": text,
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
        review = None
        if contract_id:
            try:
                contract = Contract.objects.get(id=int(contract_id), delete_time=0)
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
        "our_role_default": our_role_default,
        "core_demands_default": core_demands_default,
    }
    return render(request, "contract/ai_review.html", context)


@login_required
def ai_review_list_page(request):
    """AI合同审查 - 合同选择列表页面"""
    return render(request, "contract/ai_review_list.html")
