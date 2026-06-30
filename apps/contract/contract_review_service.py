# -*- coding: utf-8 -*-
"""AI合同审查核心服务层 - 文件解析、分条款审查、差异比对、法律咨询"""
import json
import logging
import difflib
from typing import Optional

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.ai.utils.analysis_tools import AIAnalysisTool

logger = logging.getLogger(__name__)

# ── 文档解析 ────────────────────────────────────

def parse_contract_file(file: UploadedFile) -> str:
    """解析上传的合同文件，返回纯文本内容"""
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    try:
        if ext in ("docx", "doc"):
            return _parse_docx(file)
        elif ext == "pdf":
            return _parse_pdf(file)
        elif ext in ("txt", "md", ""):
            return file.read().decode("utf-8", errors="replace")
        else:
            # 尝试当文本读取
            try:
                return file.read().decode("utf-8", errors="replace")
            except Exception:
                raise ValueError(f"不支持的文件格式: .{ext}")
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise ValueError(f"文件解析失败: {str(e)}")


def _parse_docx(file: UploadedFile) -> str:
    import io
    from docx import Document
    doc = Document(io.BytesIO(file.read()))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    # 也读表格中的文本
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    paragraphs.append(text)
    return "\n".join(paragraphs)


def _parse_pdf(file: UploadedFile) -> str:
    import io
    import fitz  # PyMuPDF
    doc = fitz.open(stream=file.read(), filetype="pdf")
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


# ── AI 合同审查核心 ──────────────────────────────

CONTRACT_REVIEW_SYSTEM_PROMPT = """你是一位资深企业法务顾问，精通《中华人民共和国民法典》《劳动合同法》《公司法》及相关司法解释。
你的任务是对合同进行逐条专业审查，输出结构化JSON格式。

审查原则：
1. 逐条分析，标注每一条款的原文摘要、风险点、风险等级、修改建议
2. 风险等级分为三级：🔴高风险(high) - 可能导致重大法律/经济损失；🟡中风险(medium) - 存在潜在纠纷隐患；🟢低风险(low) - 表述可优化但不影响核心权益
3. 修改建议必须具体、可操作，引用相关法条时标注出处
4. 对金额、期限、违约责任、管辖权条款重点审查
5. 总体评估需给出明确的签署建议：建议签署 / 建议修改后签署 / 不建议签署

返回JSON格式如下：
{
  "contract_info": {"contract_name": "", "contract_type": "", "our_role": "", "core_demands": ""},
  "overall_assessment": {"risk_level": "high/medium/low", "summary": "", "final_recommendation": ""},
  "clause_reviews": [
    {
      "clause_no": "第一条",
      "title": "条款标题",
      "original_summary": "原文摘要（直接引用原条款关键内容）",
      "risk_analysis": "风险分析（引用法条）",
      "risk_level": "high/medium/low",
      "risk_color": "🔴/🟡/🟢",
      "suggestion": "具体修改建议（含建议替换文本）"
    }
  ],
  "review_conclusion": [
    {"clause_no": "第一条", "title": "条款标题", "risk_level": "high", "action": "必须修改/建议修改/无需修改"}
  ]
}"""


class ContractReviewService:
    """AI合同审查服务"""

    def __init__(self):
        self.tool = AIAnalysisTool()

    def review_contract(
        self,
        contract_text: str,
        contract_name: str = "",
        our_role: str = "",
        core_demands: str = "",
        extra_context: Optional[str] = None,
    ) -> dict:
        """
        对合同文本进行逐条AI审查
        """
        user_prompt = f"""请对以下合同文本进行逐条专业审查：

【合同基本信息】
- 合同名称：{contract_name or "待确认"}
- 我方签约角色：{our_role or "待确认"}
- 核心诉求：{core_demands or "确保合同的合法合规性，防范法律风险"}

【合同原文】
{contract_text[:15000]}

{extra_context or ""}

请严格按照JSON格式返回审查结果，确保每条审查意见都包含原文摘要、风险分析和具体修改建议。"""
        try:
            raw_result = self.tool._call_ai(
                prompt=user_prompt,
                max_tokens=8000,
                temperature=0.2,
            )
            # 尝试解析结构化结果
            return self._parse_review_result(raw_result)
        except Exception as e:
            logger.error(f"AI审查失败: {e}", exc_info=True)
            raise

    def _parse_review_result(self, raw: dict) -> dict:
        """解析AI返回的审查结果"""
        # 如果已经是正确结构，直接返回
        if isinstance(raw, dict) and "clause_reviews" in raw:
            return raw

        # 尝试从 analysis 字段解析
        analysis = raw.get("analysis", "")
        if isinstance(analysis, dict):
            return analysis
        if isinstance(analysis, str):
            parsed = self._extract_json(analysis)
            if parsed:
                return parsed

        # 尝试从 raw 整体解析
        parsed = self._extract_json(str(raw))
        if parsed:
            return parsed

        # 兜底返回
        return {
            "contract_info": {},
            "overall_assessment": {"risk_level": "unknown", "summary": "AI分析结果解析失败，请重试", "final_recommendation": "请人工审查"},
            "clause_reviews": [],
            "review_conclusion": [],
        }

    def _extract_json(self, text: str) -> Optional[dict]:
        """从文本中提取JSON"""
        text = text.strip()
        # 去除markdown代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试找到第一个{和最后一个}
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
        return None

    def quick_review(self, contract_text: str) -> dict:
        """快速审查 - 仅返回风险评级和关键风险点"""
        prompt = f"""请快速审查以下合同，返回JSON：
{{
  "risk_level": "high/medium/low",
  "key_risks": ["风险点1", "风险点2"],
  "brief_summary": "三句话概述"
}}

合同文本：
{contract_text[:8000]}"""
        result = self.tool._call_ai(prompt=prompt, max_tokens=1500, temperature=0.2)
        return self._parse_review_result(result)

    def cross_reference_check(self, contract_text: str, system_data: dict) -> list:
        """合同原文与系统录入数据交叉校验 - AI从原文提取关键字段并与系统数据比对"""
        fields_desc = []
        for k, v in system_data.items():
            if v:
                fields_desc.append(f"  {k}: {v}")
        fields_text = "\n".join(fields_desc) if fields_desc else "无系统录入数据"

        prompt = f"""请从以下合同原文中提取关键结构化字段，并与提供的系统录入数据进行比对。

【合同原文】
{contract_text[:10000]}

【系统录入数据（供比对）】
{fields_text}

任务：
1. 从合同原文中提取以下字段的实际值：合同金额、合同开始日期、合同结束日期、签约对方名称、我方签约主体名称、合同编号
2. 将每个字段的「原文提取值」与「系统录入值」一一比对
3. 对每个字段标注匹配状态：✅ 一致 / ⚠️ 不一致 / ⊘ 原文未提及 / ⊘ 系统未录入
4. 如果不一致，说明具体差异（例如：系统录入50000元，原文写明85000元）

返回JSON数组格式：
[
  {{"field": "合同金额", "extracted_value": "85000元", "system_value": "50000元", "match": false, "status": "⚠️ 不一致", "detail": "系统录入50000元，合同原文写明85000元，差额35000元"}},
  {{"field": "合同开始日期", "extracted_value": "2025年9月1日", "system_value": "2025-09-01", "match": true, "status": "✅ 一致", "detail": ""}},
  ...
]

只返回JSON数组，不要其他文字。"""
        try:
            result = self.tool._call_ai(prompt=prompt, max_tokens=3000, temperature=0.1)
            text = result.get("analysis", "") if isinstance(result, dict) else str(result)
            if isinstance(text, str):
                text = text.strip()
                if text.startswith("```"):
                    text = text.strip("`").strip()
                    if text.lower().startswith("json"):
                        text = text[4:].strip()
                start = text.find("[")
                end = text.rfind("]")
                if start != -1 and end > start:
                    return json.loads(text[start:end + 1])
            return []
        except Exception as e:
            logger.warning(f"交叉校验失败: {e}")
            return []


# ── 合同差异比对 ─────────────────────────────────

def compare_contracts(original_text: str, compare_text: str) -> dict:
    """
    对比两份合同文本，识别差异并标注风险
    返回包含差异列表和风险标记的字典
    """
    # 按行对比
    original_lines = original_text.splitlines(keepends=True)
    compare_lines = compare_text.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, original_lines, compare_lines)
    diff_blocks = []
    risk_flags = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        block = {
            "type": tag,  # replace, delete, insert
            "original_range": [i1, i2],
            "compare_range": [j1, j2],
            "original_text": "".join(original_lines[i1:i2]).strip(),
            "compare_text": "".join(compare_lines[j1:j2]).strip(),
        }
        diff_blocks.append(block)

        # 自动风险标记：检查金额、日期、关键名词是否被改动
        risk = _detect_diff_risk(block)
        if risk:
            risk_flags.append(risk)

    summary = _generate_diff_summary(diff_blocks, risk_flags)

    return {
        "total_diffs": len(diff_blocks),
        "risk_count": len(risk_flags),
        "diff_blocks": diff_blocks,
        "risk_flags": risk_flags,
        "summary": summary,
    }


RISK_PATTERNS = [
    ("金额变更", ["元", "万元", "人民币", "美元", "¥", "$", "金额", "费用", "报酬", "补偿", "赔偿"]),
    ("日期变更", ["年", "月", "日", "期限", "截止", "有效期"]),
    ("条款删除", []),  # type=delete 时标记
    ("违约责任变更", ["违约", "赔偿", "罚", "责任"]),
    ("主体信息变更", ["甲方", "乙方", "丙方", "公司", "地址", "法定代表人"]),
]


def _detect_diff_risk(block: dict) -> Optional[dict]:
    text = block.get("original_text", "") + block.get("compare_text", "")
    for risk_name, keywords in RISK_PATTERNS:
        if not keywords:
            if block["type"] == "delete":
                return {"type": risk_name, "severity": "high", "block": block}
            continue
        for kw in keywords:
            if kw in text:
                severity = "high" if risk_name in ("金额变更", "违约责任变更") else "medium"
                return {"type": risk_name, "severity": severity, "block": block}
    return None


def _generate_diff_summary(diff_blocks: list, risk_flags: list) -> str:
    if not diff_blocks:
        return "两份合同内容完全一致，未发现差异。"
    parts = [f"共发现 {len(diff_blocks)} 处差异"]
    if risk_flags:
        high_risks = [r for r in risk_flags if r["severity"] == "high"]
        if high_risks:
            parts.append(f"，其中高风险差异 {len(high_risks)} 处（涉及金额、违约条款变更等）")
    parts.append("。建议逐项核实后再签署。")
    return "".join(parts)


# ── 法律咨询 ─────────────────────────────────────

LEGAL_QA_SYSTEM_PROMPT = """你是一位资深中国法律顾问，基于《中华人民共和国民法典》《劳动合同法》《公司法》
《合同法》及相关司法解释提供法律咨询。

回答要求：
1. 先给出【整体结论】，再展开【法律分析】，然后是【后果评估】，最后是【实操建议】
2. 引用法条时注明具体条款名称和编号
3. 对于不确定的问题，明确指出需要咨询专业律师
4. 服务对象为企业法务和管理人员，语言专业但通俗易懂
5. 回答聚焦中国法律环境"""

AI_FAILURE_HINTS = (
    "分析处理过程中遇到问题",
    "ai分析失败",
    "ai客户端不可用",
    "请稍后重试",
)


def _looks_like_ai_failure(text: str) -> bool:
    if not text:
        return True
    lowered = str(text).strip().lower()
    return any(hint in lowered for hint in AI_FAILURE_HINTS)


def _build_legal_fallback_answer(question: str) -> str:
    question_text = question or "当前法律问题"
    return (
        "【整体结论】\n"
        f"关于“{question_text}”，建议先按法定标准、证据留痕和条款明确三个原则处理，避免仅凭口头约定或笼统表述执行。\n\n"
        "【法律分析】\n"
        "企业处理合同或劳动争议相关事项时，通常应重点核对主体信息、金额计算依据、履行或支付时间、违约责任是否对等，以及是否存在法律强制性规定不得排除的权利义务。\n\n"
        "【后果评估】\n"
        "如果条款约定不清、标准低于法定要求，后续容易引发争议，可能出现补差、赔偿、仲裁诉讼或合规处罚风险。\n\n"
        "【实操建议】\n"
        "1. 明确写清金额构成、支付节点、责任边界和证据材料；\n"
        "2. 涉及劳动补偿、社保、公积金、保密、竞业限制等事项时，按现行法定标准复核；\n"
        "3. 对高风险条款保留书面沟通记录，必要时由专业律师复核后再签署。"
    )


def legal_consultation(question: str, context: str = "") -> dict:
    """
    智能法律咨询
    """
    tool = AIAnalysisTool()
    user_prompt = f"""用户问题：{question}

{context if context else ""}

请按照【整体结论】【法律分析】【后果评估】【实操建议】四个部分作答。"""
    try:
        result = tool._call_ai(
            prompt=user_prompt,
            max_tokens=3000,
            temperature=0.3,
        )
        answer = result.get("analysis", "") if isinstance(result, dict) else str(result)
        if _looks_like_ai_failure(answer):
            answer = _build_legal_fallback_answer(question)
        return {
            "success": True,
            "question": question,
            "answer": answer,
        }
    except Exception as e:
        logger.error(f"法律咨询失败: {e}", exc_info=True)
        return {"success": False, "question": question, "answer": "AI咨询服务暂时不可用，请稍后重试或联系法务部。"}


def legal_knowledge_search(query: str) -> dict:
    """
    法律法规知识查询 - 基于AI的知识检索
    """
    tool = AIAnalysisTool()
    prompt = f"""请基于中国现行法律法规，对以下查询进行解答：

查询内容：{query}

请提供：
1. 相关法律法规名称及条款
2. 核心内容摘要
3. 对企业实务的影响和建议
4. 参考司法实践或典型案例（如有）"""
    try:
        result = tool._call_ai(prompt=prompt, max_tokens=3000, temperature=0.3)
        answer = result.get("analysis", "") if isinstance(result, dict) else str(result)
        if _looks_like_ai_failure(answer):
            answer = (
                "1. 请优先检索《中华人民共和国民法典》合同编及与问题直接相关的特别法。\n"
                "2. 如涉及劳动用工，再同步核对《劳动合同法》及配套司法解释。\n"
                "3. 查询时建议重点确认：适用条款、最新修订时间、企业义务、违约或违法后果。\n"
                "4. 当前 AI 模型未返回稳定结果，建议结合权威法规库或由法务进一步复核。"
            )
        return {
            "success": True,
            "query": query,
            "results": answer,
        }
    except Exception as e:
        logger.error(f"法律知识查询失败: {e}", exc_info=True)
        return {"success": False, "query": query, "results": "查询服务暂时不可用，请稍后重试。"}


# 全局实例
contract_review_service = ContractReviewService()
