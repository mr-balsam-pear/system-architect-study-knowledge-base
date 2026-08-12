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
import importlib.util


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
        "batch_id": batch["batch_id"], "batch_file": batch["batch_file"],
        "candidate_count": len(batch["candidates"]), "warning_count": len(batch["warnings"]),
    }
    entries.append(item)
    ledger_path.write_text(json.dumps(sorted(entries, key=lambda entry: str(entry.get("batch_id", ""))), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def import_pdf_source(source_id: str, *, catalog: dict[str, dict[str, Any]] | None = None, output_root: Path = QUESTION_ROOT, answer_source_id: str = "") -> dict[str, Any]:
    """将单一台账 PDF 导入待核对层；绝不触碰已核对正式题库。"""
    if not isinstance(source_id, str) or not SAFE_SOURCE_ID.fullmatch(source_id):
        raise ValueError("source ID 格式不正确")
    catalog = catalog if catalog is not None else load_private_catalog()
    source = catalog.get(source_id)
    if not isinstance(source, dict):
        raise ValueError("source ID 未在私有真题台账登记")
    imported_at = datetime.now()
    batch_id = f"{source_id}-{imported_at.strftime('%Y%m%d-%H%M%S')}"
    batch_path = Path(output_root) / "待核对" / f"{batch_id}.json"
    suffix = 1
    while batch_path.exists():
        batch_path = Path(output_root) / "待核对" / f"{batch_id}-{suffix:02d}.json"
        suffix += 1
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
    batch["imported_at"] = imported_at.strftime("%Y-%m-%d %H:%M")
    batch["batch_id"] = batch_path.stem
    batch["batch_file"] = str(batch_path.relative_to(Path(output_root)))
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_ledger(Path(output_root), batch)
    result = {key: batch[key] for key in ("source_id", "batch_id", "batch_file", "status", "imported_at", "source", "candidates", "warnings")}
    result["batch_file"] = str(batch_path)
    return result


def _question_bank_module() -> Any:
    path = QUESTION_ROOT / "题库模型.py"
    spec = importlib.util.spec_from_file_location("review_question_bank_model", path)
    if spec is None or spec.loader is None:
        raise ValueError("无法加载题库模型")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_review_file(batch_path: Path, *, output_root: Path = QUESTION_ROOT, candidate_id: str = "") -> Path:
    """从候选批次生成单题人工核对草稿，不自动确认答案。"""
    batch = json.loads(Path(batch_path).read_text(encoding="utf-8"))
    candidates = batch.get("candidates", []) if isinstance(batch, dict) else []
    candidate = next((item for item in candidates if isinstance(item, dict) and (not candidate_id or item.get("id") == candidate_id)), None)
    if candidate is None:
        raise ValueError("批次中未找到候选题")
    source = batch.get("source", {})
    draft = {
        "id": candidate.get("id", ""), "type": candidate.get("type", ""), "status": "review_required",
        "title": "", "year": source.get("year", ""), "session": source.get("session", ""),
        "subject": source.get("subject", ""), "source": {
            "kind": source.get("kind", "local_pdf"), "source_id": batch.get("source_id", ""),
            "label": source.get("title", ""), "url": "",
        }, "knowledge_ids": [], "stem": candidate.get("stem", ""),
        "options": candidate.get("options", []), "answer": "", "explanation": "",
        "review_note": "", "candidate_answer_reference": candidate.get("answer_candidate", ""),
        "candidate_explanation_reference": candidate.get("explanation_candidate", ""),
        "review_warnings": candidate.get("warnings", []),
    }
    review_dir = Path(output_root) / "待核对" / "人工核对"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / f"{str(candidate.get('id', '')).replace(':', '_')}.json"
    if review_path.exists():
        raise ValueError("人工核对草稿已存在")
    review_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review_path


def promote_review_file(review_path: Path, *, points: list[dict[str, Any]], output_root: Path = QUESTION_ROOT) -> dict[str, str]:
    """严格校验人工核对结果并追加到正式题库，永不覆盖已有题目。"""
    draft = json.loads(Path(review_path).read_text(encoding="utf-8"))
    if not isinstance(draft, dict) or draft.get("status") != "verified":
        raise ValueError("必须完成人工核对并将 status 设为 verified")
    review_note = draft.get("review_note")
    if not isinstance(review_note, str) or "人工" not in review_note or len(review_note.strip()) < 12:
        raise ValueError("必须填写可追溯的人工核对说明")
    clean = {key: value for key, value in draft.items() if key not in {"candidate_answer_reference", "candidate_explanation_reference", "review_warnings"}}
    model = _question_bank_module()
    verified = model.validate_verified_question(clean, points)
    verified_dir = Path(output_root) / "已核对"
    verified_dir.mkdir(parents=True, exist_ok=True)
    for path in verified_dir.glob("*.json"):
        entries = json.loads(path.read_text(encoding="utf-8"))
        if any(isinstance(item, dict) and item.get("id") == verified["id"] for item in entries if isinstance(entries, list)):
            raise ValueError("正式题目 ID 已存在，不允许覆盖")
    filename = {"single_choice": "选择题.json", "case_analysis": "案例分析.json", "essay": "论文.json"}[verified["type"]]
    target = verified_dir / filename
    entries = json.loads(target.read_text(encoding="utf-8")) if target.exists() else []
    if not isinstance(entries, list):
        raise ValueError("正式题库文件必须是数组")
    entries.append(verified)
    target.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"id": verified["id"], "file": str(target)}


def load_knowledge_points(path: Path = ROOT / "site" / "knowledge-data.js") -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"window\.KNOWLEDGE_POINT_DATA\s*=\s*(\[.*\])\s*;?\s*\Z", text, re.S)
    if not match:
        raise ValueError("无法读取知识点目录")
    value = json.loads(match.group(1))
    if not isinstance(value, list):
        raise ValueError("知识点目录必须是数组")
    return [item for item in value if isinstance(item, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description="题库导入、人工核对草稿与安全提升")
    parser.add_argument("--action", choices=("import", "review", "promote"), default="import")
    parser.add_argument("--source-id", default="", help="import 时的私有真题台账 ID")
    parser.add_argument("--answer-source-id", default="", help="import 时可选的答案解析台账 ID")
    parser.add_argument("--batch-file", default="", help="review 时的待核对批次 JSON")
    parser.add_argument("--candidate-id", default="", help="review 时要生成草稿的候选题 ID")
    parser.add_argument("--review-file", default="", help="promote 时已由人工完成的核对 JSON")
    args = parser.parse_args()
    if args.action == "import":
        if not args.source_id:
            parser.error("import 必须提供 --source-id")
        result = import_pdf_source(args.source_id, answer_source_id=args.answer_source_id)
        print(json.dumps({**result, "candidate_count": len(result["candidates"])}, ensure_ascii=False, indent=2))
    elif args.action == "review":
        if not args.batch_file:
            parser.error("review 必须提供 --batch-file")
        print(create_review_file(Path(args.batch_file), candidate_id=args.candidate_id))
    else:
        if not args.review_file:
            parser.error("promote 必须提供 --review-file")
        print(json.dumps(promote_review_file(Path(args.review_file), points=load_knowledge_points()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
