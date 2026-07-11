"""Supply Chain AI service layer – wraps AIAnalysisTool for all 6 modules."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from decimal import Decimal

from apps.ai.utils.analysis_tools import AIAnalysisTool


logger = logging.getLogger(__name__)


class SupplyChainAIService:
    """Unified AI service that delegates to the project global AIAnalysisTool."""

    def __init__(self) -> None:
        self._tool = AIAnalysisTool()
        self.timeout_seconds = 8

    def _call(self, prompt: str, max_tokens: int = 1200, temperature: float = 0.2) -> dict[str, object]:
        """Call the global AI tool and return a dict-safe result."""
        ai_client = getattr(self._tool, "ai_client", None)
        original_timeout = getattr(ai_client, "timeout", None)
        original_retries = getattr(ai_client, "max_retries", None)
        original_retry_delay = getattr(ai_client, "retry_delay", None)

        if ai_client is not None:
            if hasattr(ai_client, "timeout"):
                ai_client.timeout = min(original_timeout or self.timeout_seconds, self.timeout_seconds)
            if hasattr(ai_client, "max_retries"):
                ai_client.max_retries = 0
            if hasattr(ai_client, "retry_delay"):
                ai_client.retry_delay = 0

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            self._tool._call_ai,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            result = future.result(timeout=self.timeout_seconds)
            return self._extract_json(result)
        except TimeoutError:
            future.cancel()
            logger.warning("Supply chain AI call timed out after %s seconds", self.timeout_seconds)
            return {"content": "AI响应超时，已使用系统业务规则兜底，请稍后刷新获取模型建议。"}
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            if ai_client is not None:
                if original_timeout is not None and hasattr(ai_client, "timeout"):
                    ai_client.timeout = original_timeout
                if original_retries is not None and hasattr(ai_client, "max_retries"):
                    ai_client.max_retries = original_retries
                if original_retry_delay is not None and hasattr(ai_client, "retry_delay"):
                    ai_client.retry_delay = original_retry_delay

    # ------------------------------------------------------------------
    # 1. Demand Forecast
    # ------------------------------------------------------------------
    def generate_forecast(
        self,
        product_name: str,
        historical_demand: list[Decimal],
        inventory_quantity: Decimal,
        wip_quantity: Decimal,
        safety_stock: Decimal,
    ) -> dict[str, object]:
        prompt = (
            f"你是一名耳机行业供应链计划专家。请基于以下信息生成供需预测建议，输出纯 JSON。\n"
            f"产品：{product_name}\n"
            f"近几期历史需求：{[str(d) for d in historical_demand]}\n"
            f"当前库存：{inventory_quantity}\n"
            f"在制数量：{wip_quantity}\n"
            f"安全库存基准：{safety_stock}\n\n"
            "只返回 JSON，格式：\n"
            '{"predicted_quantity": 预计需求数量(float), '
            '"recommended_quantity": 建议备料量(float), '
            '"confidence": AI置信度(0-100的float), '
            '"risk_level": "high/medium/low", '
            '"summary": "一段50字内的中文预测摘要"}\n\n'
            "JSON:"
        )
        return self._call(prompt, max_tokens=800)

    def answer_forecast_question(
        self,
        plan_name: str,
        predicted_quantity: Decimal,
        recommended_quantity: Decimal,
        risk_level: str,
        confidence: float,
        question: str,
    ) -> str:
        prompt = (
            "你是一名供应链需求分析师，请根据已有预测结果回答用户问题，用中文精简回答。\n"
            f"预测计划：{plan_name}\n"
            f"预测量：{predicted_quantity}，建议备料量：{recommended_quantity}\n"
            f"风险等级：{risk_level}，置信度：{confidence}%\n"
            f"用户问题：{question}\n\n"
            "直接给出回答，不超过120字。"
        )
        result = self._call(prompt, max_tokens=300, temperature=0.3)
        return str(result.get("content") or result.get("summary") or "")

    # ------------------------------------------------------------------
    # 2. Inventory Analysis
    # ------------------------------------------------------------------
    def analyze_inventory_risk(
        self,
        total_items: int,
        high_risk_count: int,
        medium_risk_count: int,
        dead_stock_count: int,
        safety_breach_count: int,
        top_risk_items: list[str],
    ) -> str:
        prompt = (
            "你是一名库存管理专家。请基于以下库存风险指标生成一份80字内的中文库存体检摘要，指出最值得关注的风险和一条行动建议。\n"
            f"物料总数：{total_items}，高风险(低于安全库存)：{high_risk_count}，中风险：{medium_risk_count}\n"
            f"呆滞物料：{dead_stock_count}，安全库存不达标：{safety_breach_count}\n"
            f"TOP风险物料示例：{'; '.join(top_risk_items[:5])}\n\n"
            "直接输出摘要文本，不用JSON。"
        )
        result = self._call(prompt, max_tokens=300, temperature=0.3)
        return str(result.get("content") or result.get("summary") or "")

    # ------------------------------------------------------------------
    # 3. Outsource Issue
    # ------------------------------------------------------------------
    def outsource_completeness_advice(
        self,
        order_code: str,
        total_items: int,
        shortage_count: int,
        shortage_details: list[str],
    ) -> str:
        prompt = (
            "你是一名 PMC 物料控制专家。请根据委外发料齐套校验结果给出60字以内的跟进建议。\n"
            f"委外单号：{order_code}，总物料项：{total_items}，缺料项：{shortage_count}\n"
            f"缺料明细：{'; '.join(shortage_details[:5])}\n\n"
            "直接输出建议文本，不用JSON。"
        )
        result = self._call(prompt, max_tokens=300, temperature=0.2)
        return str(result.get("content") or result.get("summary") or "")

    # ------------------------------------------------------------------
    # 4. PR Review
    # ------------------------------------------------------------------
    def evaluate_pr(
        self,
        scenario: str,
        order_type: str,
        is_urgent: bool,
        lt_shortage: bool,
        tail_order: bool,
        npi_trial: bool,
        rework_order: bool,
    ) -> dict[str, object]:
        prompt = (
            "你是一名采购审核员。请判断以下采购申请PR是否需要人工复核，输出纯 JSON。\n"
            f"场景：{scenario}，订单类型：{order_type}，是否紧急：{is_urgent}\n"
            f"LT不足：{lt_shortage}，尾数订单：{tail_order}，NPI试产：{npi_trial}，返工单：{rework_order}\n\n"
            "只返回 JSON，格式：\n"
            '{"is_abnormal": true/false, '
            '"recommended_action": "approve/urgent_approve/manual_review/filter", '
            '"reason": "中文审核理由，50字内", '
            '"risk_level": "high/medium/low"}\n\n'
            "JSON:"
        )
        return self._call(prompt, max_tokens=500, temperature=0.1)

    # ------------------------------------------------------------------
    # 5. Price Review
    # ------------------------------------------------------------------
    def parse_spec_document(self, raw_text: str) -> dict[str, object]:
        prompt = (
            "你是一名耳机行业采购工程师。请从以下规格书文本中提取成本相关字段，输出纯 JSON。\n"
            "需要提取的字段：" + "、".join([
                "material_cost材料成本", "process_cost工艺成本", "labor_cost人工成本",
                "loss_cost损耗成本", "package_cost包装成本", "logistics_cost物流成本",
                "profit_cost利润"
            ]) + "\n"
            f"规格书文本：\n{raw_text[:3000]}\n\n"
            "只返回 JSON，字段值均为 float 数字，格式："
            '{"material_cost": float, "process_cost": float, "labor_cost": float, '
            '"loss_cost": float, "package_cost": float, "logistics_cost": float, "profit_cost": float}\n\n'
            "JSON:"
        )
        return self._call(prompt, max_tokens=600, temperature=0.1)

    def analyze_price_review(
        self,
        item_name: str,
        quoted_price: Decimal,
        component_summary: str,
        market_price: Decimal,
        history_avg: Decimal,
    ) -> dict[str, object]:
        prompt = (
            "你是一名采购核价专家。请基于成本拆解和基准价格，判断报价是否合理，输出纯 JSON。\n"
            f"物料：{item_name}，报价单价：{quoted_price}\n"
            f"成本拆解摘要：{component_summary}\n"
            f"市场参考价：{market_price}，历史均价：{history_avg}\n\n"
            "只返回 JSON，格式：\n"
            '{"result": "approved/exception", '
            '"risk_level": "high/medium/low", '
            '"summary": "80字内中文复核结论", '
            '"abnormal_items": ["异常成本项名称"], '
            '"negotiation_points": ["议价方向建议"]}\n\n'
            "JSON:"
        )
        return self._call(prompt, max_tokens=800, temperature=0.2)

    # ------------------------------------------------------------------
    # 6. Sample Management
    # ------------------------------------------------------------------
    def suggest_sample_priority(
        self,
        pending_count: int,
        overdue_count: int,
        overdue_details: list[str],
    ) -> str:
        prompt = (
            "你是一名研发项目助理。请根据打样待领情况，给出50字以内的处理优先级建议。\n"
            f"当前待领样：{pending_count}，超期未领：{overdue_count}\n"
            + (f"超期明细：{'; '.join(overdue_details[:3])}" if overdue_details else "暂无超期") + "\n\n"
            "直接输出建议文本，不用JSON。"
        )
        result = self._call(prompt, max_tokens=250, temperature=0.3)
        return str(result.get("content") or result.get("summary") or "")

    # ------------------------------------------------------------------
    # Utility: Structured JSON extract
    # ------------------------------------------------------------------
    def _extract_json(self, raw: object) -> dict[str, object]:
        if isinstance(raw, dict):
            if raw.get("error") and not raw.get("analysis") and not raw.get("content"):
                return {}
            for key in ("analysis", "data", "result", "content"):
                nested = raw.get(key)
                if isinstance(nested, dict) and any(k in nested for k in ("predicted_quantity", "result", "is_abnormal", "material_cost")):
                    return nested
                if isinstance(nested, str):
                    parsed = self._extract_json(nested)
                    if parsed and parsed.get("content") != nested:
                        return parsed
                    if key in {"analysis", "content"} and nested.strip():
                        return {"content": nested.strip()}
            return raw
        raw_str = str(raw or "").strip()
        if raw_str.startswith("```"):
            raw_str = raw_str.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return {"content": raw_str}


supply_chain_ai = SupplyChainAIService()
