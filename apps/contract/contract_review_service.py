# -*- coding: utf-8 -*-
"""AI合同审查核心服务层 - 文件解析、分条款审查、差异比对、法律咨询"""
import ast
import json
import logging
import difflib
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from typing import Optional

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.ai.utils.analysis_tools import AIAnalysisTool

logger = logging.getLogger(__name__)

RISK_LEVEL_LABELS = {
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
    "unknown": "待确认",
}

REVIEW_SINGLE_PASS_LIMIT = 6000
REVIEW_CHUNK_TARGET = 4500
REVIEW_MAX_CHUNKS = 4
QUICK_REVIEW_TEXT_LIMIT = 5000

# ── 文档解析 ────────────────────────────────────


def _rewind_file(file: UploadedFile) -> None:
    """尽量将上传文件指针复位到开头。"""
    try:
        file.seek(0)
    except Exception:
        pass


def _read_file_bytes(file: UploadedFile) -> bytes:
    """读取上传文件的全部字节，并复位文件指针。"""
    _rewind_file(file)
    data = file.read()
    _rewind_file(file)
    return data


def _extract_xml_text(xml_bytes: bytes) -> str:
    """从 Office XML 节点中尽量抽取可读文本。"""
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return ""

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for para in root.findall(f".//{ns}p"):
        parts = [text.strip() for text in para.itertext() if text and text.strip()]
        if parts:
            paragraphs.append("".join(parts))

    if paragraphs:
        return "\n".join(paragraphs)

    raw_text = " ".join(text.strip() for text in root.itertext() if text and text.strip())
    return raw_text


def _extract_office_package_text(file_bytes: bytes) -> str:
    """对非标准/异常 Office OOXML 包做兜底抽取。"""
    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        return ""

    candidates = []
    priority_names = [
        "word/document.xml",
        "word/header1.xml",
        "word/header2.xml",
        "word/header3.xml",
        "word/footer1.xml",
        "word/footer2.xml",
        "word/footer3.xml",
        "word/comments.xml",
        "word/footnotes.xml",
        "word/endnotes.xml",
    ]

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        names = zf.namelist()
        ordered_names = [name for name in priority_names if name in names]
        ordered_names.extend(
            sorted(
                name for name in names
                if name.endswith(".xml") and name not in ordered_names
            )
        )

        seen = set()
        for name in ordered_names:
            if name in seen:
                continue
            seen.add(name)
            try:
                text = _extract_xml_text(zf.read(name))
            except Exception:
                continue
            if text.strip():
                candidates.append(text.strip())
            if len("\n\n".join(candidates)) > 20000:
                break

    return "\n\n".join(candidates).strip()

def parse_contract_file(file: UploadedFile) -> str:
    """解析上传的合同文件，返回纯文本内容"""
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    try:
        if ext in ("docx", "doc"):
            return _parse_docx(file)
        elif ext == "pdf":
            return _parse_pdf(file)
        elif ext in ("txt", "md", ""):
            return _read_file_bytes(file).decode("utf-8", errors="replace")
        else:
            # 尝试当文本读取
            try:
                return _read_file_bytes(file).decode("utf-8", errors="replace")
            except Exception:
                raise ValueError(f"不支持的文件格式: .{ext}")
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise ValueError(f"文件解析失败: {str(e)}")


def _parse_docx(file: UploadedFile) -> str:
    from docx import Document
    file_bytes = _read_file_bytes(file)

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        fallback_text = _extract_office_package_text(file_bytes)
        if fallback_text.strip():
            logger.warning("标准 docx 解析失败，已启用 OOXML 兜底抽取: %s", exc)
            return fallback_text
        raise ValueError(
            "Word 文档解析失败，请确认文件是标准 .docx/.doc 格式，"
            "并且没有损坏或误传成其他 Office 文件。"
        ) from exc

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
    import fitz  # PyMuPDF
    doc = fitz.open(stream=_read_file_bytes(file), filetype="pdf")
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
        segments = self._split_contract_for_review(contract_text)
        partial_results = []
        last_raw = None

        for idx, segment in enumerate(segments, start=1):
            user_prompt = self._build_review_prompt(
                contract_text=segment["text"],
                contract_name=contract_name,
                our_role=our_role,
                core_demands=core_demands,
                extra_context=extra_context,
                chunk_index=idx,
                chunk_total=len(segments),
            )
            retry_prompt = (
                user_prompt
                + "\n\n再次提醒：只返回一个合法 JSON 对象，不要输出 markdown 代码块，不要补充解释文字。"
            )
            parsed = None
            for attempt, prompt in enumerate((user_prompt, retry_prompt), start=1):
                try:
                    raw_result = self.tool._call_ai(
                        prompt=prompt,
                        max_tokens=3200,
                        temperature=0.2,
                    )
                    last_raw = raw_result
                    parsed = self._parse_review_result(raw_result)
                    if self._is_valid_review_result(parsed):
                        partial_results.append(
                            self._ensure_review_defaults(
                                parsed,
                                contract_name=contract_name,
                                our_role=our_role,
                                core_demands=core_demands,
                            )
                        )
                        break
                    logger.warning(
                        "AI合同审查分段结果第%s段第%s次解析不完整，准备继续重试。",
                        idx,
                        attempt,
                    )
                except Exception as e:
                    logger.error(f"AI审查第{idx}段第{attempt}次调用失败: {e}", exc_info=True)

            if parsed is None or not self._is_valid_review_result(parsed):
                partial_results.append(
                    self._build_review_fallback(
                        contract_text=segment["text"],
                        contract_name=contract_name,
                        our_role=our_role,
                        core_demands=core_demands,
                        raw_result=last_raw,
                    )
                )

        merged = self._merge_review_results(
            partial_results,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
        )
        if self._is_valid_review_result(merged):
            return merged

        return self._build_review_fallback(
            contract_text=contract_text,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
            raw_result=last_raw,
        )

    def _build_review_prompt(
        self,
        contract_text: str,
        contract_name: str = "",
        our_role: str = "",
        core_demands: str = "",
        extra_context: Optional[str] = None,
        chunk_index: int = 1,
        chunk_total: int = 1,
    ) -> str:
        chunk_hint = ""
        if chunk_total > 1:
            chunk_hint = (
                f"\n【分段信息】\n"
                f"当前仅审查第 {chunk_index}/{chunk_total} 段合同内容。\n"
                f"请只输出当前段落中实际出现的条款审查意见，不要臆造未出现的条款。"
            )

        return f"""请对以下合同文本进行逐条专业审查：

【合同基本信息】
- 合同名称：{contract_name or "待确认"}
- 我方签约角色：{our_role or "待确认"}
- 核心诉求：{core_demands or "确保合同的合法合规性，防范法律风险"}
{chunk_hint}

【合同原文】
{contract_text}

{extra_context or ""}

请严格按照JSON格式返回审查结果，确保每条审查意见都包含原文摘要、风险分析和具体修改建议。"""

    def _split_contract_for_review(self, contract_text: str) -> list[dict]:
        text = str(contract_text or "").strip()
        if not text:
            return [{"text": "", "index": 1}]

        if len(text) <= REVIEW_SINGLE_PASS_LIMIT:
            return [{"text": text, "index": 1}]

        clause_segments = []
        current_lines = []
        pattern = re.compile(r"^\s*(第[一二三四五六七八九十百千万0-9]+条|\d+[、.．])")
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                if current_lines:
                    current_lines.append("")
                continue
            if pattern.match(line) and current_lines:
                clause_segments.append("\n".join(current_lines).strip())
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            clause_segments.append("\n".join(current_lines).strip())

        if len(clause_segments) <= 1:
            clause_segments = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not clause_segments:
            clause_segments = [text]

        chunks = []
        current_chunk = []
        current_len = 0
        for segment in clause_segments:
            segment = segment.strip()
            if not segment:
                continue
            segment_len = len(segment) + (2 if current_chunk else 0)
            if current_chunk and current_len + segment_len > REVIEW_CHUNK_TARGET:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [segment]
                current_len = len(segment)
            else:
                current_chunk.append(segment)
                current_len += segment_len
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        if not chunks:
            chunks = [text]

        if len(chunks) > REVIEW_MAX_CHUNKS:
            total = len(chunks)
            merged_chunks = []
            group_size = (total + REVIEW_MAX_CHUNKS - 1) // REVIEW_MAX_CHUNKS
            for start in range(0, total, group_size):
                merged_chunks.append("\n\n".join(chunks[start:start + group_size]))
            chunks = merged_chunks[:REVIEW_MAX_CHUNKS]

        return [{"text": chunk, "index": idx + 1} for idx, chunk in enumerate(chunks)]

    def _parse_review_result(self, raw: dict) -> Optional[dict]:
        """解析AI返回的审查结果"""
        candidates = []
        if isinstance(raw, dict):
            candidates.append(raw)
            for key in ("analysis", "data", "result", "output", "response", "content"):
                value = raw.get(key)
                if value:
                    candidates.append(value)
        elif raw:
            candidates.append(raw)

        for candidate in candidates:
            normalized = self._normalize_review_payload(candidate)
            if normalized:
                return normalized
        return None

    def _normalize_review_payload(self, payload) -> Optional[dict]:
        if isinstance(payload, dict):
            if "clause_reviews" in payload or "overall_assessment" in payload:
                return payload

            for key in ("analysis", "data", "result", "output", "response", "content"):
                nested = payload.get(key) if isinstance(payload, dict) else None
                if not nested:
                    continue
                normalized = self._normalize_review_payload(nested)
                if normalized:
                    return normalized

        if isinstance(payload, str):
            parsed = self._extract_json(payload)
            if isinstance(parsed, dict):
                return self._normalize_review_payload(parsed)

        return None

    def _is_valid_review_result(self, result: Optional[dict]) -> bool:
        if not isinstance(result, dict):
            return False

        overall = result.get("overall_assessment") or {}
        summary = str(overall.get("summary", "")).strip()
        clauses = result.get("clause_reviews") or []
        return bool(summary or clauses)

    def _merge_review_results(
        self,
        results: list,
        contract_name: str = "",
        our_role: str = "",
        core_demands: str = "",
    ) -> dict:
        merged_clauses = []
        merged_conclusion = []
        contract_info = {
            "contract_name": contract_name or "",
            "contract_type": "",
            "our_role": our_role or "",
            "core_demands": core_demands or "",
        }
        fallback_used = False

        for result in results:
            if not isinstance(result, dict):
                continue
            info = result.get("contract_info") or {}
            if isinstance(info, dict):
                for key in ("contract_name", "contract_type", "our_role", "core_demands"):
                    if not contract_info.get(key) and info.get(key):
                        contract_info[key] = info.get(key)
            fallback_used = fallback_used or bool(result.get("fallback_used"))

            for clause in result.get("clause_reviews") or []:
                if not isinstance(clause, dict):
                    continue
                merged_clauses.append({
                    "clause_no": clause.get("clause_no", ""),
                    "title": clause.get("title", ""),
                    "original_summary": clause.get("original_summary", ""),
                    "risk_analysis": clause.get("risk_analysis", ""),
                    "risk_level": self._normalize_risk_level(clause.get("risk_level")),
                    "risk_color": clause.get("risk_color", ""),
                    "suggestion": clause.get("suggestion", ""),
                })

        deduped_clauses = []
        seen = set()
        for clause in merged_clauses:
            key = (
                clause.get("clause_no", "").strip(),
                clause.get("title", "").strip(),
                clause.get("original_summary", "").strip()[:80],
            )
            if key in seen:
                continue
            seen.add(key)
            deduped_clauses.append(clause)

        deduped_clauses.sort(key=self._clause_sort_key)
        for clause in deduped_clauses:
            merged_conclusion.append({
                "clause_no": clause.get("clause_no", ""),
                "title": clause.get("title", ""),
                "risk_level": clause.get("risk_level", "unknown"),
                "action": self._risk_level_to_action(clause.get("risk_level", "unknown")),
            })

        overall = self._build_overall_assessment_from_clauses(deduped_clauses, fallback_used)
        result = {
            "contract_info": contract_info,
            "overall_assessment": overall,
            "clause_reviews": deduped_clauses,
            "review_conclusion": merged_conclusion,
        }
        if fallback_used:
            result["fallback_used"] = True
        return self._ensure_review_defaults(
            result,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
        )

    def _build_overall_assessment_from_clauses(self, clauses: list, fallback_used: bool = False) -> dict:
        if not clauses:
            return {
                "risk_level": "unknown",
                "summary": "未识别到可审查条款，请确认合同正文是否完整。",
                "final_recommendation": "请人工审查",
            }

        high_count = sum(1 for clause in clauses if clause.get("risk_level") == "high")
        medium_count = sum(1 for clause in clauses if clause.get("risk_level") == "medium")
        low_count = sum(1 for clause in clauses if clause.get("risk_level") == "low")

        risk_level = "high" if high_count else ("medium" if medium_count else "low")
        top_titles = [
            f"{clause.get('clause_no')}{('[' + clause.get('title', '') + ']') if clause.get('title') else ''}"
            for clause in clauses
            if clause.get("risk_level") in ("high", "medium")
        ][:3]

        summary = (
            f"本次按条款分段完成审查，共识别 {len(clauses)} 个条款，"
            f"其中高风险 {high_count} 项、中风险 {medium_count} 项、低风险 {low_count} 项。"
        )
        if top_titles:
            summary += "建议优先处理：" + "、".join(top_titles) + "。"
        if fallback_used:
            summary += "部分段落已启用兜底审查结果，请结合原文再复核。"

        recommendation = "建议修改后签署" if risk_level in ("high", "medium") else "可签署，但建议保留审查记录"
        return {
            "risk_level": risk_level,
            "summary": summary,
            "final_recommendation": recommendation,
        }

    def _risk_level_to_action(self, risk_level: str) -> str:
        normalized = self._normalize_risk_level(risk_level)
        if normalized == "high":
            return "必须修改"
        if normalized == "medium":
            return "建议修改"
        if normalized == "low":
            return "无需修改"
        return "建议复核"

    def _clause_sort_key(self, clause: dict):
        clause_no = str(clause.get("clause_no", ""))
        match = re.search(r"(\d+)", clause_no)
        if match:
            return int(match.group(1)), clause_no
        chinese_order = "零一二三四五六七八九十百千万"
        score = sum((chinese_order.find(char) + 1) for char in clause_no if char in chinese_order)
        return (score or 9999), clause_no

    def _extract_json(self, text: str) -> Optional[dict]:
        """从文本中提取JSON"""
        text = self._strip_code_fence(text)
        if not text:
            return None

        for candidate in self._iter_json_candidates(text, "{", "}"):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(candidate)
                except (ValueError, SyntaxError):
                    continue
                if isinstance(parsed, dict):
                    return parsed
        return None

    def _strip_code_fence(self, text: str) -> str:
        text = str(text or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _iter_json_candidates(self, text: str, start_char: str, end_char: str):
        yield text

        start = text.find(start_char)
        while start != -1:
            depth = 0
            for idx in range(start, len(text)):
                char = text[idx]
                if char == start_char:
                    depth += 1
                elif char == end_char:
                    depth -= 1
                    if depth == 0:
                        yield text[start:idx + 1]
                        break
            start = text.find(start_char, start + 1)

    def quick_review(self, contract_text: str) -> dict:
        """快速审查 - 仅返回风险评级和关键风险点"""
        prompt = f"""请快速审查以下合同，返回JSON：
{{
  "risk_level": "high/medium/low",
  "key_risks": ["风险点1", "风险点2"],
  "brief_summary": "三句话概述"
}}

合同文本：
{contract_text[:QUICK_REVIEW_TEXT_LIMIT]}"""
        retry_prompt = prompt + "\n\n只返回 JSON，不要输出任何解释文字。"
        for idx, current_prompt in enumerate((prompt, retry_prompt), start=1):
            result = self.tool._call_ai(prompt=current_prompt, max_tokens=1500, temperature=0.2)
            parsed = self._parse_quick_review_result(result)
            if self._is_valid_quick_review(parsed):
                return parsed
            logger.warning("AI快速评估结果第%s次解析不完整，准备继续重试。", idx)

        return self._build_quick_review_fallback(contract_text, result)

    def _parse_quick_review_result(self, raw) -> Optional[dict]:
        candidates = []
        if isinstance(raw, dict):
            candidates.append(raw)
            for key in ("analysis", "data", "result", "output", "response", "content"):
                value = raw.get(key)
                if value:
                    candidates.append(value)
        elif raw:
            candidates.append(raw)

        for candidate in candidates:
            normalized = self._normalize_quick_review_payload(candidate)
            if normalized:
                return normalized
        return None

    def _normalize_quick_review_payload(self, payload) -> Optional[dict]:
        if isinstance(payload, dict):
            if any(key in payload for key in ("risk_level", "brief_summary", "key_risks")):
                return {
                    "risk_level": self._normalize_risk_level(payload.get("risk_level")),
                    "key_risks": self._normalize_key_risks(payload.get("key_risks")),
                    "brief_summary": str(
                        payload.get("brief_summary")
                        or payload.get("summary")
                        or payload.get("analysis")
                        or ""
                    ).strip(),
                }

            for key in ("analysis", "data", "result", "output", "response", "content"):
                nested = payload.get(key)
                if not nested:
                    continue
                normalized = self._normalize_quick_review_payload(nested)
                if normalized:
                    return normalized

        if isinstance(payload, str):
            parsed = self._extract_json(payload)
            if isinstance(parsed, dict):
                normalized = self._normalize_quick_review_payload(parsed)
                if normalized:
                    return normalized

            summary, risks = self._extract_quick_review_from_text(payload)
            if summary or risks:
                return {
                    "risk_level": self._infer_risk_level_from_text(payload),
                    "key_risks": risks,
                    "brief_summary": summary,
                }

        return None

    def _extract_quick_review_from_text(self, text: str) -> tuple[str, list]:
        cleaned = self._strip_code_fence(text)
        lines = [line.strip(" -•\t") for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return "", []

        risks = []
        summary_parts = []
        for line in lines:
            if any(keyword in line for keyword in ("风险", "问题", "注意", "建议")) and len(risks) < 4:
                risks.append(line)
            elif len(summary_parts) < 3:
                summary_parts.append(line)

        summary = " ".join(summary_parts[:3]).strip()
        return summary, risks

    def _is_valid_quick_review(self, result: Optional[dict]) -> bool:
        if not isinstance(result, dict):
            return False
        return bool(result.get("brief_summary") or result.get("key_risks"))

    def _normalize_risk_level(self, value) -> str:
        text = str(value or "").strip().lower()
        mapping = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "unknown": "unknown",
            "高": "high",
            "高风险": "high",
            "中": "medium",
            "中风险": "medium",
            "低": "low",
            "低风险": "low",
            "待确认": "unknown",
        }
        for key, normalized in mapping.items():
            if key and key in text:
                return normalized
        return "unknown"

    def _normalize_key_risks(self, risks) -> list:
        if isinstance(risks, list):
            return [str(item).strip() for item in risks if str(item).strip()][:5]
        if isinstance(risks, str):
            parts = re.split(r"[；;\n]+", risks)
            return [part.strip(" -•") for part in parts if part.strip()][:5]
        return []

    def _infer_risk_level_from_text(self, text: str) -> str:
        lowered = str(text or "").lower()
        if "高风险" in lowered or "重大" in lowered:
            return "high"
        if "中风险" in lowered or "需重点关注" in lowered or "建议修改" in lowered:
            return "medium"
        if "低风险" in lowered or "风险较低" in lowered:
            return "low"
        return "unknown"

    def _ensure_review_defaults(
        self,
        result: dict,
        contract_name: str = "",
        our_role: str = "",
        core_demands: str = "",
    ) -> dict:
        fallback_used = bool(result.get("fallback_used"))
        normalized = {
            "contract_info": result.get("contract_info") if isinstance(result.get("contract_info"), dict) else {},
            "overall_assessment": result.get("overall_assessment") if isinstance(result.get("overall_assessment"), dict) else {},
            "clause_reviews": result.get("clause_reviews") if isinstance(result.get("clause_reviews"), list) else [],
            "review_conclusion": result.get("review_conclusion") if isinstance(result.get("review_conclusion"), list) else [],
        }

        contract_info = normalized["contract_info"]
        contract_info.setdefault("contract_name", contract_name or "")
        contract_info.setdefault("contract_type", contract_info.get("contract_type", "") or "")
        contract_info.setdefault("our_role", our_role or "")
        contract_info.setdefault("core_demands", core_demands or "")

        overall = normalized["overall_assessment"]
        overall["risk_level"] = self._normalize_risk_level(overall.get("risk_level"))
        overall["summary"] = str(overall.get("summary", "")).strip()
        overall["final_recommendation"] = str(overall.get("final_recommendation", "")).strip()

        cleaned_clauses = []
        for idx, clause in enumerate(normalized["clause_reviews"], start=1):
            if not isinstance(clause, dict):
                continue
            cleaned_clauses.append({
                "clause_no": clause.get("clause_no") or f"第{idx}条",
                "title": str(clause.get("title", "")).strip(),
                "original_summary": str(clause.get("original_summary", "")).strip(),
                "risk_analysis": str(clause.get("risk_analysis", "")).strip(),
                "risk_level": self._normalize_risk_level(clause.get("risk_level")),
                "risk_color": clause.get("risk_color") or "",
                "suggestion": str(clause.get("suggestion", "")).strip(),
            })
        normalized["clause_reviews"] = cleaned_clauses

        cleaned_conclusion = []
        for item in normalized["review_conclusion"]:
            if not isinstance(item, dict):
                continue
            cleaned_conclusion.append({
                "clause_no": item.get("clause_no", ""),
                "title": item.get("title", ""),
                "risk_level": self._normalize_risk_level(item.get("risk_level")),
                "action": item.get("action", ""),
            })
        normalized["review_conclusion"] = cleaned_conclusion

        if not overall["summary"] and cleaned_clauses:
            high_count = sum(1 for clause in cleaned_clauses if clause["risk_level"] == "high")
            medium_count = sum(1 for clause in cleaned_clauses if clause["risk_level"] == "medium")
            overall["summary"] = (
                f"本次共识别 {len(cleaned_clauses)} 个条款，"
                f"其中高风险 {high_count} 项、中风险 {medium_count} 项。"
            )
        if not overall["final_recommendation"] and overall["risk_level"] != "unknown":
            overall["final_recommendation"] = (
                "建议修改后签署" if overall["risk_level"] in ("high", "medium") else "可签署，但建议保留审查记录"
            )

        if fallback_used:
            normalized["fallback_used"] = True

        return normalized

    def _build_quick_review_fallback(self, contract_text: str, raw_result=None) -> dict:
        key_risks = []
        lowered = contract_text or ""
        if any(keyword in lowered for keyword in ("金额", "费用", "价款", "付款")):
            key_risks.append("请重点核对金额口径、付款节点和触发条件是否写清。")
        if any(keyword in lowered for keyword in ("违约", "赔偿", "责任")):
            key_risks.append("请重点检查违约责任是否对等、违约金比例是否合理。")
        if any(keyword in lowered for keyword in ("争议", "仲裁", "法院")):
            key_risks.append("请核对争议解决条款是否约定明确且对我方有利。")
        if not key_risks:
            key_risks.append("AI 未返回稳定的结构化结果，建议结合逐条审查再次确认付款、违约责任和期限条款。")

        risk_level = "medium" if key_risks else "unknown"
        if any(keyword in lowered for keyword in ("双倍", "立即解除", "单方决定")):
            risk_level = "high"

        hint = ""
        if isinstance(raw_result, dict):
            hint = str(raw_result.get("analysis", "")).strip()
        summary = (
            "已完成快速扫描。系统优先给出可执行的风险焦点，适合先判断是否需要进入逐条审查。"
        )
        if _looks_like_ai_failure(hint):
            summary = "AI 返回不稳定，本次已自动切换为规则化快速评估，建议继续使用“开始AI审查”获取更完整意见。"

        return {
            "risk_level": risk_level,
            "key_risks": key_risks[:3],
            "brief_summary": summary,
            "fallback_used": True,
        }

    def _build_review_fallback(
        self,
        contract_text: str,
        contract_name: str = "",
        our_role: str = "",
        core_demands: str = "",
        raw_result=None,
    ) -> dict:
        clause_reviews = []
        text = contract_text or ""
        clause_patterns = re.split(r"\n(?=第[一二三四五六七八九十百0-9]+条|\d+[、.])", text)
        candidate_clauses = [item.strip() for item in clause_patterns if item.strip()][:6]
        if not candidate_clauses and text.strip():
            candidate_clauses = [text[:1200].strip()]

        for idx, clause_text in enumerate(candidate_clauses, start=1):
            clause_no_match = re.match(r"(第[一二三四五六七八九十百0-9]+条|\d+[、.])", clause_text)
            clause_no = clause_no_match.group(1) if clause_no_match else f"第{idx}条"
            title = ""
            lines = [line.strip() for line in clause_text.splitlines() if line.strip()]
            if lines:
                title = lines[0][:20]

            analysis = "建议人工重点复核本条款的金额、履行条件、责任边界和时间节点。"
            suggestion = "建议补充明确金额口径、履行触发条件、违约责任和争议解决方式。"
            risk_level = "medium"
            joined = " ".join(lines[:4]) if lines else clause_text

            if any(keyword in joined for keyword in ("违约", "赔偿", "双倍")):
                analysis = "该条涉及违约或赔偿责任，若责任不对等或违约金过高，后续争议风险较高。"
                suggestion = "建议细化违约情形，并确保双方责任对等、违约金与实际损失相匹配。"
                risk_level = "high" if "双倍" in joined else "medium"
            elif any(keyword in joined for keyword in ("金额", "费用", "付款", "价款")):
                analysis = "该条涉及金额或付款安排，若未明确付款节点、条件或口径，容易引发履约争议。"
                suggestion = "建议写明金额构成、付款时间、付款条件及逾期处理方式。"
            elif any(keyword in joined for keyword in ("期限", "日期", "起", "止")):
                analysis = "该条涉及期限或生效时间，建议确认起止日期、触发条件及顺延规则是否明确。"
                suggestion = "建议明确起算时间、终止条件及特殊情形下的处理方式。"
            elif any(keyword in joined for keyword in ("争议", "仲裁", "法院")):
                analysis = "该条涉及争议解决安排，需确认约定管辖和适用规则是否清晰。"
                suggestion = "建议明确争议解决机构、管辖法院或仲裁地，并校验是否对我方有利。"
                risk_level = "low"

            clause_reviews.append({
                "clause_no": clause_no,
                "title": title or "合同条款",
                "original_summary": joined[:180],
                "risk_analysis": analysis,
                "risk_level": risk_level,
                "risk_color": "",
                "suggestion": suggestion,
            })

        overall_risk_level = "high" if any(item["risk_level"] == "high" for item in clause_reviews) else "medium"
        raw_hint = ""
        if isinstance(raw_result, dict):
            raw_hint = str(raw_result.get("analysis", "")).strip()
        summary = "AI 本次未返回稳定的结构化逐条结果，系统已自动切换为规则化兜底审查，请重点复核付款、责任和期限条款。"
        if not _looks_like_ai_failure(raw_hint) and raw_hint:
            summary = "AI 返回内容格式不稳定，系统已自动整理为可读的兜底审查结果，建议再执行一次完整审查确认。"

        result = {
            "contract_info": {
                "contract_name": contract_name or "",
                "contract_type": "",
                "our_role": our_role or "",
                "core_demands": core_demands or "",
            },
            "overall_assessment": {
                "risk_level": overall_risk_level if clause_reviews else "unknown",
                "summary": summary,
                "final_recommendation": "建议修改后签署" if clause_reviews else "请人工审查",
            },
            "clause_reviews": clause_reviews,
            "review_conclusion": [
                {
                    "clause_no": item["clause_no"],
                    "title": item["title"],
                    "risk_level": item["risk_level"],
                    "action": "必须修改" if item["risk_level"] == "high" else "建议修改",
                }
                for item in clause_reviews[:6]
            ],
            "fallback_used": True,
        }
        return self._ensure_review_defaults(
            result,
            contract_name=contract_name,
            our_role=our_role,
            core_demands=core_demands,
        )

    def cross_reference_check(self, contract_text: str, system_data: dict) -> list:
        """合同原文与系统录入数据交叉校验 - 本地规则提取并比对。"""
        text = str(contract_text or "")
        extracted = self._extract_contract_structured_fields(text)
        field_alias = {
            "合同编号": "合同编号",
            "合同名称": "合同名称",
            "合同金额": "合同金额",
            "客户名称": "签约对方名称",
            "签约主体": "我方签约主体名称",
            "合同开始时间": "合同开始日期",
            "合同结束时间": "合同结束日期",
            "签订时间": "签订时间",
        }

        results = []
        for field, system_value in system_data.items():
            extracted_field = field_alias.get(field, field)
            extracted_value = extracted.get(extracted_field, "")
            results.append(
                self._build_cross_check_item(
                    field=field,
                    extracted_value=extracted_value,
                    system_value=system_value,
                )
            )
        return results

    def _build_cross_check_item(self, field: str, extracted_value: str = "", system_value: str = "") -> dict:
        extracted_value = str(extracted_value or "").strip()
        system_value = str(system_value or "").strip()

        if not extracted_value and not system_value:
            return {
                "field": field,
                "extracted_value": "",
                "system_value": "",
                "match": True,
                "status": "⊘ 系统未录入",
                "detail": "",
            }

        if not extracted_value:
            return {
                "field": field,
                "extracted_value": "",
                "system_value": system_value,
                "match": False,
                "status": "⊘ 原文未提及",
                "detail": "合同原文中未识别到该字段，请人工核对。",
            }

        if not system_value:
            return {
                "field": field,
                "extracted_value": extracted_value,
                "system_value": "",
                "match": False,
                "status": "⊘ 系统未录入",
                "detail": "系统中未录入该字段，建议补充。",
            }

        matched = self._values_match(field, extracted_value, system_value)
        return {
            "field": field,
            "extracted_value": extracted_value,
            "system_value": system_value,
            "match": matched,
            "status": "✅ 一致" if matched else "⚠️ 不一致",
            "detail": "" if matched else f"系统录入为 {system_value}，合同原文识别为 {extracted_value}。",
        }

    def _extract_contract_structured_fields(self, text: str) -> dict:
        return {
            "合同编号": self._extract_contract_code(text),
            "合同名称": self._extract_contract_name(text),
            "合同金额": self._extract_contract_amount(text),
            "签约对方名称": self._extract_party_name(text, ("乙方", "客户", "买方", "委托方")),
            "我方签约主体名称": self._extract_party_name(text, ("甲方", "我方", "卖方", "服务方")),
            "合同开始日期": self._extract_field_date(text, ("开始日期", "合同开始时间", "服务期限自", "自")),
            "合同结束日期": self._extract_field_date(text, ("结束日期", "合同结束时间", "服务期限至", "至")),
            "签订时间": self._extract_field_date(text, ("签订时间", "签署日期", "签约时间")),
        }

    def _extract_contract_code(self, text: str) -> str:
        patterns = [
            r"(?:合同编号|编号|协议编号)[:：]?\s*([A-Za-z0-9\-_\/]+)",
            r"\b([A-Z]{1,6}-\d{2,}-[A-Za-z0-9\-]+)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_contract_name(self, text: str) -> str:
        patterns = [
            r"(?:合同名称|协议名称|文件名称)[:：]?\s*([^\n]{2,80})",
            r"^\s*([^\n]{2,60}(?:合同|协议书|协议))\s*$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_contract_amount(self, text: str) -> str:
        patterns = [
            r"(?:合同金额|总金额|价款|合同价|金额)[:：]?\s*(人民币)?\s*([0-9]+(?:\.[0-9]+)?)\s*(万元|元)?",
            r"([0-9]+(?:\.[0-9]+)?)\s*(万元|元)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = [group for group in match.groups() if group]
                return "".join(groups).strip()
        return ""

    def _extract_party_name(self, text: str, labels: tuple) -> str:
        for label in labels:
            match = re.search(rf"{label}[:：]?\s*([^\n]{{2,80}})", text)
            if match:
                value = match.group(1).strip()
                value = re.split(r"[，,；;。]", value)[0].strip()
                return value
        return ""

    def _extract_field_date(self, text: str, labels: tuple) -> str:
        for label in labels:
            match = re.search(
                rf"{re.escape(label)}[^\n]*?((?:20\d{{2}}|19\d{{2}})[年\-/\.]\d{{1,2}}[月\-/\.]\d{{1,2}}日?)",
                text
            )
            if match:
                return match.group(1).strip()
        generic_dates = self._extract_all_dates(text)
        if "开始" in "".join(labels) and generic_dates:
            return generic_dates[0]
        if "结束" in "".join(labels) and len(generic_dates) > 1:
            return generic_dates[1]
        if "签订" in "".join(labels) and generic_dates:
            return generic_dates[0]
        return ""

    def _extract_all_dates(self, text: str) -> list:
        matches = re.findall(r"((?:20\d{2}|19\d{2})[年\-/\.]\d{1,2}[月\-/\.]\d{1,2}日?)", text)
        return [match.strip() for match in matches]

    def _values_match(self, field: str, extracted_value: str, system_value: str) -> bool:
        if field == "合同金额":
            return self._normalize_amount_text(extracted_value) == self._normalize_amount_text(system_value)
        if "时间" in field:
            return self._normalize_date_text(extracted_value) == self._normalize_date_text(system_value)
        return self._normalize_compare_text(extracted_value) == self._normalize_compare_text(system_value)

    def _normalize_amount_text(self, value: str) -> str:
        value = str(value or "").replace(",", "").replace("，", "").replace("人民币", "").strip()
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(万元|元)?", value)
        if not match:
            return self._normalize_compare_text(value)
        number = float(match.group(1))
        unit = match.group(2) or "元"
        if unit == "万元":
            number *= 10000
        return f"{number:.2f}"

    def _normalize_date_text(self, value: str) -> str:
        digits = re.findall(r"\d+", str(value or ""))
        if len(digits) >= 3:
            year, month, day = digits[0], digits[1].zfill(2), digits[2].zfill(2)
            return f"{year}-{month}-{day}"
        return self._normalize_compare_text(value)

    def _normalize_compare_text(self, value: str) -> str:
        return re.sub(r"[\s:：\-_/\.（）()，,；;]", "", str(value or "")).lower()


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
