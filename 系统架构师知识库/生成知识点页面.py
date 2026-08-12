#!/usr/bin/env python3
"""从 XMind 源稿生成可直接学习的知识点 Markdown 页面和站点数据。

输入仅限当前工作区已提取的教材文字层；不会读取或复制外部真题项目内容。
"""

from __future__ import annotations

import json
import html
import re
import shutil
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "2026下半年系统架构师备考资料" / "xmind" / "源稿"
BASE_DIR = ROOT / "系统架构师知识库"
CHAPTER_DIR = BASE_DIR / "01-知识点" / "章节"
POINT_DIR = BASE_DIR / "01-知识点" / "小节"
SITE_DATA = BASE_DIR / "site" / "knowledge-data.js"

CHAPTER_RE = re.compile(r"^# 第(\d+)章\s+(.+?)\s*$")
SECTION_RE = re.compile(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$")
SUBSECTION_RE = re.compile(r"^\s*-\s+(\d+(?:\.\d+){2,})\s+(.+?)\s*$")
REVIEW_RE = re.compile(r"^\s*-\s+复习要点：\s*(.*)$")
BODY_RE = re.compile(r"^\s*-\s+教材正文：\s*(.*)$")
SOURCE_RE = re.compile(r"^>\s*来源：`?([^`；]+)`?")


def natural_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def safe_name(value: str) -> str:
    return value.replace("/", "-")


def markdown_destination(value: str) -> str:
    """用 Markdown 的尖括号目标语法包裹相对路径。

    这能让含半角括号的知识点文件名不被 Markdown 解析器提前截断。
    """
    return f"<{value.replace('<', '%3C').replace('>', '%3E')}>"


def markdown_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def paragraphs(text: str) -> list[str]:
    """保持全部文字，同时按中文句末标点切分，改善教材文字层可读性。"""
    if not text:
        return []
    chunks = re.split(r"(?<=[。！？；])\s*", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def excerpt(sentences: list[str], pattern: str, fallback: str) -> str:
    matcher = re.compile(pattern)
    selected = [sentence for sentence in sentences if matcher.search(sentence)]
    return (selected[0] if selected else fallback).strip()


def make_summary(record: dict) -> str:
    review = record.get("review", "")
    if review:
        return f"{record['title']}：{review}"
    source = record["source_paragraphs"]
    if source:
        return f"{record['title']}：{source[0]}"
    return f"围绕“{record['title']}”建立概念、机制与应用边界的理解。"


def enrich(record: dict) -> None:
    source = record["source_paragraphs"]
    fallback = source[0] if source else "本节未提取到可识别教材文字，请回源 PDF 核对图表、公式和上下文。"
    record["summary"] = make_summary(record)
    record["structured"] = {
        "定义/关注点": excerpt(source, r"定义|是指|关注|目的|概念|作用|重要", fallback),
        "机制/组成": excerpt(source, r"包括|组成|通过|过程|步骤|模型|方法|结构|机制|原则|阶段|类型|特征", fallback),
        "场景/限制": excerpt(source, r"适用|场景|限制|风险|问题|注意|优点|缺点|挑战|影响|条件", "结合本节教材原文核对适用条件、约束与取舍。"),
    }
    record["exam_use"] = {
        "综合知识": "先辨析本节的定义、组成、术语和边界；将易混概念放在同一张对比卡中复习。",
        "案例分析": "从题干中定位本节涉及的目标、约束和机制，再以教材术语组织“问题—措施—验证”的答案。",
        "论文应用": "若论文主题相关，用项目中的背景、本人决策、实施过程和可验证效果来落地本节知识，避免只罗列概念。",
    }
    tags = [record["chapter_title"], record["section_title"], record["title"]]
    tags.extend(re.findall(r"[A-Za-z][A-Za-z0-9+./-]{1,}|[\u4e00-\u9fff]{2,6}", record["summary"]))
    record["tags"] = list(OrderedDict.fromkeys(tags))[:18]
    if source:
        items = "".join(f"<li>{html.escape(item)}</li>" for item in source)
        record["source_html"] = f'<ul class="source-paragraphs">{items}</ul>'
    else:
        record["source_html"] = (
            '<p class="source-placeholder">本节未提取到可识别教材文字；'
            '请回源 PDF 核对图表、公式和上下文。</p>'
        )


def parse_file(path: Path) -> dict:
    chapter: dict | None = None
    sections: list[dict] = []
    current_section: dict | None = None
    current_point: dict | None = None
    source_ref = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        if match := CHAPTER_RE.match(line):
            chapter = {"id": match.group(1), "title": match.group(2), "source": "", "sections": sections}
            continue
        if match := SOURCE_RE.match(line):
            source_ref = match.group(1).strip().replace("`", "")
            if chapter:
                chapter["source"] = source_ref
            continue
        if match := SECTION_RE.match(line):
            current_section = {
                "id": match.group(1), "title": match.group(2), "review": "", "body": "", "children": [],
                "source": source_ref,
            }
            sections.append(current_section)
            current_point = current_section
            continue
        if match := SUBSECTION_RE.match(line):
            if current_section is None:
                continue
            current_point = {
                "id": match.group(1), "title": match.group(2), "review": "", "body": "", "children": [],
                "source": source_ref,
            }
            current_section["children"].append(current_point)
            continue
        if match := REVIEW_RE.match(line):
            if current_section:
                current_section["review"] = match.group(1).strip()
            continue
        if match := BODY_RE.match(line):
            if current_point:
                current_point["body"] = match.group(1).strip()

    if chapter is None:
        raise ValueError(f"无法识别章节标题：{path}")
    return chapter


def records_from_chapter(chapter: dict) -> list[dict]:
    records: list[dict] = []
    for section in chapter["sections"]:
        # 每个一级节都有独立概览页。如果文字层没有一级节正文，则聚合
        # 子节正文，保证目录节点可学习，又不杜撰教材之外的事实。
        section_record = dict(section)
        if not section_record["body"]:
            section_record["body"] = "".join(child["body"] for child in section["children"] if child["body"])
        records.append(normalize_record(chapter, section, section_record, "section"))
        for point in section["children"]:
            # 教材文字层能识别出标题却无正文时，仍生成明确的回源占位页，
            # 不因 PDF 提取缺口跳过教材编号。
            records.append(normalize_record(chapter, section, point, "subsection"))
    return records


def normalize_record(chapter: dict, section: dict, point: dict, kind: str) -> dict:
    record = {
        "id": point["id"],
        "chapter": chapter["id"],
        "chapter_title": chapter["title"],
        "section": section["id"],
        "section_title": section["title"],
        "title": point["title"],
        "review": point["review"] or section["review"],
        "source_paragraphs": paragraphs(point["body"]),
        "chapter_source": chapter["source"],
        "kind": kind,
    }
    enrich(record)
    return record


def point_markdown(record: dict, previous: dict | None, following: dict | None) -> str:
    structured = "\n".join(f"### {heading}\n\n- {content}" for heading, content in record["structured"].items())
    exam_use = "\n".join(f"### {heading}\n\n- {content}" for heading, content in record["exam_use"].items())
    original = "\n".join(f"- {text}" for text in record["source_paragraphs"]) or "- 本节未提取到可识别教材文字；请回源 PDF 核对图表、公式和上下文。"
    if previous:
        prev_label = markdown_label(f"上一知识点：{previous['id']} {previous['title']}")
        prev_target = markdown_destination(f"./{previous['file_name']}")
        prev_link = f"[{prev_label}]({prev_target})"
    else:
        prev_link = "- 已是当前知识库的第一个知识点。"
    if following:
        next_label = markdown_label(f"下一知识点：{following['id']} {following['title']}")
        next_target = markdown_destination(f"./{following['file_name']}")
        next_link = f"[{next_label}]({next_target})"
    else:
        next_link = "- 已是当前知识库的最后一个知识点。"
    return f"""# {record['id']} {record['title']}

> 所属：第{record['chapter']}章 {record['chapter_title']} → {record['section']} {record['section_title']}

## 核心结论

{record['summary']}

## 结构化理解

{structured}

## 易错与答题

{exam_use}

## 教材原文展开

> 以下为当前工作区教材 PDF 文字层的分段整理；图、表、公式图片请回源 PDF 核对。

{original}

## 关联导航

- [返回第{record['chapter']}章概览]({markdown_destination(f"../章节/{record['chapter_file_name']}")})
- {prev_link}
- {next_link}

## 来源

- 教材章节：`{record['chapter_source']}`
- 本页由 `生成知识点页面.py` 从当前工作区 XMind 源稿生成；不含外部真题项目的正文。
"""


def chapter_markdown(chapter: dict, records: list[dict]) -> str:
    record_map = {record["id"]: record for record in records}
    parts = [f"# 第{chapter['id']}章 {chapter['title']}", "", f"> 教材来源：`{chapter['source']}`", "", "## 学习说明", "", "先点击每个知识点阅读精炼结论，再展开教材文字层核对细节。图、表、公式图片请回源 PDF。", "", "## 章节目录", ""]
    for section in chapter["sections"]:
        parts.extend([f"### {section['id']} {section['title']}", ""])
        if section["review"]:
            parts.extend([f"- 复习要点：{section['review']}", ""])
        if section["id"] in record_map:
            record = record_map[section["id"]]
            label = markdown_label(f"直接学习：{record['id']} {record['title']}")
            destination = markdown_destination(f"../小节/{record['file_name']}")
            parts.extend([f"- [{label}]({destination})", ""])
        for child in section["children"]:
            record = record_map.get(child["id"])
            if record:
                label = markdown_label(f"{record['id']} {record['title']}")
                destination = markdown_destination(f"../小节/{record['file_name']}")
                parts.extend([f"- [{label}]({destination})", ""])
    parts.extend(["## 来源", "", f"- `{chapter['source']}`", ""])
    return "\n".join(parts)


def main() -> None:
    chapters = [parse_file(path) for path in sorted(SOURCE_DIR.glob("*.md"))]
    if len(chapters) != 20:
        raise ValueError(f"预期 20 章源稿，实际为 {len(chapters)}")

    if CHAPTER_DIR.parent.exists():
        shutil.rmtree(CHAPTER_DIR.parent)
    CHAPTER_DIR.mkdir(parents=True)
    POINT_DIR.mkdir(parents=True)

    records: list[dict] = []
    for chapter in chapters:
        records.extend(records_from_chapter(chapter))
    records.sort(key=lambda item: natural_key(item["id"]))
    if len({record['id'] for record in records}) != len(records):
        raise ValueError("检测到重复知识点编号")

    for index, record in enumerate(records):
        record["file_name"] = f"{safe_name(record['id'])}-{safe_name(record['title'])}.md"
        record["chapter_file_name"] = f"{int(record['chapter']):02d}-{safe_name(record['chapter_title'])}.md"
        record["markdownPath"] = f"../01-知识点/小节/{record['file_name']}"
        record["prevId"] = records[index - 1]["id"] if index else None
        record["nextId"] = records[index + 1]["id"] if index + 1 < len(records) else None

    for index, record in enumerate(records):
        previous = records[index - 1] if index else None
        following = records[index + 1] if index + 1 < len(records) else None
        (POINT_DIR / record["file_name"]).write_text(point_markdown(record, previous, following), encoding="utf-8")

    for chapter in chapters:
        chapter_records = [record for record in records if record["chapter"] == chapter["id"]]
        name = f"{int(chapter['id']):02d}-{safe_name(chapter['title'])}.md"
        (CHAPTER_DIR / name).write_text(chapter_markdown(chapter, chapter_records), encoding="utf-8")

    browser_records = []
    for record in records:
        browser_records.append({key: record[key] for key in (
            "id", "chapter", "chapter_title", "section", "section_title", "title", "summary", "structured",
            "exam_use", "tags", "source_paragraphs", "source_html", "prevId", "nextId", "chapter_source", "markdownPath", "kind",
        )})
    SITE_DATA.write_text("window.KNOWLEDGE_POINT_DATA = " + json.dumps(browser_records, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"已生成 {len(chapters)} 个章节概览、{len(records)} 个可读知识点页及站点数据。")


if __name__ == "__main__":
    main()
