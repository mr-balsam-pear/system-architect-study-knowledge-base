#!/usr/bin/env python3
"""从外部本机项目的文件名生成元数据台账；不会复制或读取 PDF 正文。"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIELDS = ["id", "year", "session", "subject", "material_type", "title", "absolute_path", "source_root", "origin", "status", "notes"]


def parse_year(value: str) -> str:
    match = re.search(r"(20\d{2})", value)
    return match.group(1) if match else "未识别"


def parse_session(value: str) -> str:
    if "上半年" in value or "05" in value:
        return "上半年"
    if "下半年" in value or "11" in value:
        return "下半年"
    return "未标注"


def parse_subject(value: str) -> str:
    if "答案" in value or "解析" in value:
        return "答案解析"
    if "论文" in value:
        return "论文"
    if "案例" in value or "下午真题" in value:
        return "案例分析"
    if "综合" in value or "上午真题" in value:
        return "综合知识"
    return "综合包"


def parse_type(value: str) -> str:
    if "回忆" in value:
        return "回忆版"
    if "答案" in value or "解析" in value:
        return "答案解析"
    return "真题"


def collect_rows(question_root: Path, source_root: Path):
    rows = []
    for path in sorted(question_root.rglob("*.pdf")):
        combined = f"{path.parent.name} {path.name}"
        year = parse_year(combined)
        subject = parse_subject(combined)
        rows.append({
            "id": f"q{len(rows) + 1:03d}",
            "year": year,
            "session": parse_session(combined),
            "subject": subject,
            "material_type": parse_type(combined),
            "title": path.stem,
            "absolute_path": str(path),
            "source_root": str(SOURCE_ROOT),
            "origin": "本机 system_architect-main 项目（仅索引）",
            "status": "需确认版权与版本",
            "notes": "本知识库未复制或嵌入此文件；仅供本机有权访问者导航使用。",
        })
    return rows


def write_csv(rows, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_js(rows, output_path: Path):
    site_rows = [{key: row[key] for key in ("id", "year", "session", "subject", "material_type", "title", "absolute_path", "status")} for row in rows]
    payload = "window.KNOWLEDGE_BASE_DATA = " + json.dumps(site_rows, ensure_ascii=False, indent=2) + ";\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="从已获授权的本机 PDF 目录生成私有真题索引")
    parser.add_argument("--source-root", required=True, help="本机资料根目录；不会写入公开仓库")
    parser.add_argument("--question-dir", default="03、历年真题(2009年-2025年)+答案解析", help="相对 source-root 的真题目录")
    args = parser.parse_args()
    source_root = Path(args.source_root).expanduser().resolve()
    question_root = source_root / args.question_dir
    if not question_root.is_dir():
        raise SystemExit("指定的真题目录不存在")
    csv_path = BASE / "02-真题索引" / "真题台账.csv"
    js_path = BASE / "site" / "data.js"
    rows = collect_rows(question_root, source_root)
    write_csv(rows, csv_path)
    write_js(rows, js_path)
    print(json.dumps({"records": len(rows), "csv": str(csv_path), "data": str(js_path)}, ensure_ascii=False))
