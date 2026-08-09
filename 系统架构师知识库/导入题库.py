#!/usr/bin/env python3
"""将已登记的本机真题 PDF 提取为待人工核对的题库批次。

本工具不会扫描外部目录，不会复制 PDF，也不会把提取结果自动提升为正式题目。
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parent
PRIVATE_CATALOG_FILE = ROOT / "真题台账私有.json"
QUESTION_ROOT = ROOT / "题库数据"
SAFE_SOURCE_ID = re.compile(r"[A-Za-z0-9_-]+\Z")
MAX_PAGES = 100
MAX_CHARS_PER_PAGE = 6000


def extract_pdf_text(path: Path, max_pages: int = MAX_PAGES, max_chars_per_page: int = MAX_CHARS_PER_PAGE) -> str:
    """提取有限 PDF 文字层，失败时由导入批次记录警告。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("未安装 pypdf，无法提取 PDF 文字层") from exc
    try:
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "")[:max_chars_per_page] for page in reader.pages[:max_pages])
    except Exception as exc:
        raise RuntimeError(f"PDF 文本提取失败：{exc}") from exc


def load_private_catalog(path: Path = PRIVATE_CATALOG_FILE) -> dict[str, dict[str, Any]]:
    """加载私有白名单，确保只有已登记的精确 source ID 可被导入。"""
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("私有真题台账必须是数组")
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_id = entry.get("id")
        absolute_path = entry.get("absolute_path")
        if isinstance(source_id, str) and SAFE_SOURCE_ID.fullmatch(source_id) and isinstance(absolute_path, str):
            if source_id in result:
                raise ValueError(f"私有真题台账 source ID 重复：{source_id}")
            result[source_id] = dict(entry)
    return result


def _clean_extracted(value: str, maximum: int = 8000) -> str:
    return re.sub(r"\s+", " ", value).strip()[:maximum]


def _candidate_choice_blocks(text: str, source_id: str) -> list[dict[str, Any]]:
    """识别明确编号和 A-D 选项行；答案一律留空，等待人工确认。"""
    candidates: list[dict[str, Any]] = []
    pattern = re.compile(
        r"[（(](\d{1,3})[）)]\s*A[.．、]\s*(.*?)\s+B[.．、]\s*(.*?)\s+C[.．、]\s*(.*?)\s+D[.．、]\s*(.*?)(?=\s*[（(]\d{1,3}[）)]\s*A[.．、]|\n●|\Z)",
        re.S,
    )
    previous_end = 0
    for match in pattern.finditer(text):
        options = [{"label": label, "text": _clean_extracted(match.group(index), 3000)} for index, label in enumerate("ABCD", start=2)]
        if all(option["text"] for option in options):
            number = match.group(1)
            before = text[previous_end:match.start()]
            marker = before.rfind("●")
            stem = _clean_extracted(before[marker + 1:] if marker >= 0 else before, 3000)
            if not stem:
                stem = f"第 {number} 题（题干提取不完整，请回看原 PDF）"
            candidates.append({
                "id": f"{source_id}:choice-{int(number):02d}",
                "type": "single_choice",
                "status": "candidate",
                "stem": stem,
                "options": options,
                "answer_candidate": "",
                "explanation_candidate": "",
                "warnings": ["自动规则分段；答案与解析未提取，必须人工核对。"],
            })
        previous_end = match.end()
    return candidates[:100]


def _answer_groups(text: str) -> list[tuple[list[str], str]]:
    """提取答案 PDF 中的答案串和其后的解析候选，不将它们视作正式答案。"""
    groups: list[tuple[list[str], str]] = []
    pattern = re.compile(r"【答案】\s*([A-D](?:\s+[A-D]){0,5})\s*【解析】\s*(.*?)(?=【答案】|\Z)", re.S)
    for match in pattern.finditer(text):
        answers = re.findall(r"[A-D]", match.group(1))
        explanation = _clean_extracted(match.group(2), 3000)
        if answers:
            groups.append((answers, explanation))
    return groups


def _attach_answer_candidates(candidates: list[dict[str, Any]], answer_text: str) -> None:
    """按解析文件中出现的答案顺序附加候选答案，数量不一致时保留警告。"""
    answers: list[str] = []
    explanations: list[str] = []
    for group_answers, explanation in _answer_groups(answer_text):
        answers.extend(group_answers)
        explanations.extend([explanation] * len(group_answers))
    for index, candidate in enumerate(candidates):
        if index >= len(answers):
            candidate["warnings"].append("未在答案解析 PDF 中找到对应候选答案。")
            continue
        candidate["answer_candidate"] = answers[index]
        candidate["explanation_candidate"] = explanations[index]
        candidate["warnings"].append("候选答案/解析按解析 PDF 顺序配对，必须人工核对题号与内容。")


def _batch_record(source_id: str, source: dict[str, Any], raw_text: str, warnings: list[str], answer_text: str = "") -> dict[str, Any]:
    candidates = _candidate_choice_blocks(raw_text, source_id)
    if answer_text:
        _attach_answer_candidates(candidates, answer_text)
    if not candidates:
        warnings.append("未可靠识别出完整选择题块；请根据原始文字和 PDF 人工整理。")
    return {
        "source_id": source_id,
        "status": "needs_review",
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": {
            "year": str(source.get("year", "")),
            "session": str(source.get("session", "")),
            "subject": str(source.get("subject", "")),
            "title": str(source.get("title", "")),
            "kind": "local_pdf",
        },
        "raw_text": raw_text,
        "candidates": candidates,
        "warnings": warnings,
    }


def _update_ledger(root: Path, batch: dict[str, Any]) -> None:
    ledger_path = root / "待核对" / "导入批次台账.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists():
        try:
            entries = json.loads(ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("导入批次台账格式错误") from exc
    else:
        entries = []
    if not isinstance(entries, list):
        raise ValueError("导入批次台账必须是数组")
    item = {
        "source_id": batch["source_id"], "status": batch["status"], "imported_at": batch["imported_at"],
        "year": batch["source"]["year"], "subject": batch["source"]["subject"],
        "candidate_count": len(batch["candidates"]), "warning_count": len(batch["warnings"]),
    }
    entries = [entry for entry in entries if isinstance(entry, dict) and entry.get("source_id") != batch["source_id"]]
    entries.append(item)
    ledger_path.write_text(json.dumps(sorted(entries, key=lambda entry: str(entry.get("source_id", ""))), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def import_pdf_source(source_id: str, *, catalog: dict[str, dict[str, Any]] | None = None, output_root: Path = QUESTION_ROOT, replace: bool = False, answer_source_id: str = "") -> dict[str, Any]:
    """将单一台账 PDF 导入待核对层；绝不触碰已核对正式题库。"""
    if not isinstance(source_id, str) or not SAFE_SOURCE_ID.fullmatch(source_id):
        raise ValueError("source ID 格式不正确")
    catalog = catalog if catalog is not None else load_private_catalog()
    source = catalog.get(source_id)
    if not isinstance(source, dict):
        raise ValueError("source ID 未在私有真题台账登记")
    batch_path = Path(output_root) / "待核对" / f"{source_id}.json"
    if batch_path.exists() and not replace:
        raise ValueError("待核对批次已存在；如需重新提取请使用 --replace")
    warnings = ["仅规则分段，必须人工核对题干、选项、答案和解析。"]
    raw_text = ""
    path = source.get("absolute_path")
    if not isinstance(path, str) or not Path(path).is_file():
        warnings.append("登记的 PDF 文件不存在或不可读取；未提取文字。")
    else:
        try:
            raw_text = extract_pdf_text(Path(path))
        except RuntimeError as exc:
            warnings.append(str(exc))
    answer_text = ""
    if answer_source_id:
        if not SAFE_SOURCE_ID.fullmatch(answer_source_id) or answer_source_id not in catalog:
            raise ValueError("答案解析 source ID 未在私有真题台账登记")
        answer_path = catalog[answer_source_id].get("absolute_path")
        if not isinstance(answer_path, str) or not Path(answer_path).is_file():
            warnings.append("登记的答案解析 PDF 不存在或不可读取；未提取候选答案。")
        else:
            try:
                answer_text = extract_pdf_text(Path(answer_path))
                warnings.append(f"已使用答案解析台账 {answer_source_id} 生成候选答案与解析；必须人工核对。")
            except RuntimeError as exc:
                warnings.append(f"答案解析 PDF 提取失败：{exc}")
    batch = _batch_record(source_id, source, raw_text, warnings, answer_text)
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_ledger(Path(output_root), batch)
    return {key: batch[key] for key in ("source_id", "status", "imported_at", "source", "candidates", "warnings")}


def main() -> None:
    parser = argparse.ArgumentParser(description="导入单一登记 PDF 到待核对互动题库批次")
    parser.add_argument("--source-id", required=True, help="私有真题台账中的精确 ID，例如 q002")
    parser.add_argument("--replace", action="store_true", help="仅覆盖同 source ID 的待核对批次")
    parser.add_argument("--answer-source-id", default="", help="同年度答案解析 PDF 的私有台账 ID，例如 q003")
    args = parser.parse_args()
    result = import_pdf_source(args.source_id, replace=args.replace, answer_source_id=args.answer_source_id)
    print(json.dumps({**result, "candidate_count": len(result["candidates"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
