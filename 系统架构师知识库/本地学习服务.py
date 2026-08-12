#!/usr/bin/env python3
"""只为本知识库提供静态页面和已登记真题的本机预览服务。

服务不会扫描外部目录；真题文件只能由 site/data.js 中登记的 ID 映射取得。
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import importlib.util
import json
import logging
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import re
from typing import Any
import unicodedata
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT / "site"
PRIVATE_CATALOG_FILE = ROOT / "真题台账私有.json"
KNOWLEDGE_FILE = SITE_ROOT / "knowledge-data.js"
STUDY_ROOT = ROOT / "学习档案"
QUESTION_BANK_ROOT = ROOT / "题库数据"
PODCAST_ROOT = ROOT.parent / "章节播客"
PODCAST_CATALOG = {
    "1": {"chapter": "1", "title": "绪论", "filename": "", "duration_seconds": 0},
    "2": {"chapter": "2", "title": "计算机系统的硬件组成", "filename": "第02章-计算机系统的硬件组成.wav", "duration_seconds": 2429},
    "3": {"chapter": "3", "title": "信息系统的基本概念与功能", "filename": "第03章-信息系统的基本概念与功能.wav", "duration_seconds": 2143},
    "4": {"chapter": "4", "title": "系统规划", "filename": "", "duration_seconds": 0},
    "5": {"chapter": "5", "title": "软件工程中的常见开发方法", "filename": "第05章-软件工程中的常见开发方法.wav", "duration_seconds": 2350},
    "6": {"chapter": "6", "title": "数据库系统中数据模型的三要素", "filename": "第06章-数据库系统中数据模型的三要素.wav", "duration_seconds": 2157},
    "7": {"chapter": "7", "title": "软件架构设计的不同阶段", "filename": "第07章-软件架构设计的不同阶段.wav", "duration_seconds": 3171},
    "8": {"chapter": "8", "title": "软件系统质量属性及评估", "filename": "第08章-软件系统质量属性及评估.wav", "duration_seconds": 2061},
    "9": {"chapter": "9", "title": "软件可靠性的定义与定量描述", "filename": "第09章-软件可靠性的定义与定量描述.wav", "duration_seconds": 2680},
    "10": {"chapter": "10", "title": "软件架构的演化与维护", "filename": "第10章-软件架构的演化与维护.wav", "duration_seconds": 3012},
    "11": {"chapter": "11", "title": "信息物理系统技术概述", "filename": "第11章-信息物理系统技术概述.wav", "duration_seconds": 2591},
    "12": {"chapter": "12", "title": "信息系统架构的基本概念与发展", "filename": "第12章-信息系统架构的基本概念与发展.wav", "duration_seconds": 2220},
    "13": {"chapter": "13", "title": "层次式架构及相关设计模式", "filename": "第13章-层次式架构及相关设计模式.wav", "duration_seconds": 2088},
    "14": {"chapter": "14", "title": "云原生架构：释放云计算技术红利", "filename": "第14章-云原生架构：释放云计算技术红利.wav", "duration_seconds": 3435},
    "15": {"chapter": "15", "title": "SOA+ 的发展历程与标准", "filename": "第15章-SOA+的发展历程与标准.wav", "duration_seconds": 2943},
    "16": {"chapter": "16", "title": "嵌入式系统的硬件组成与分类", "filename": "第16章-嵌入式系统的硬件组成与分类.wav", "duration_seconds": 2303},
    "17": {"chapter": "17", "title": "通信系统网络架构的演进", "filename": "第17章-通信系统网络架构的演进.wav", "duration_seconds": 2510},
    "18": {"chapter": "18", "title": "安全架构设计的主要内容", "filename": "第18章-安全架构设计的主要内容.wav", "duration_seconds": 2225},
    "19": {"chapter": "19", "title": "大数据架构设计面临的挑战", "filename": "第19章-大数据架构设计面临的挑战.wav", "duration_seconds": 2499},
    "20": {"chapter": "20", "title": "系统架构师论文写作要点", "filename": "第20章-系统架构师论文写作要点.wav", "duration_seconds": 1013},
}
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+\Z")
SAFE_PRACTICE_ID = re.compile(r"[A-Za-z0-9:_-]+\Z")
SAFE_KNOWLEDGE_ID = re.compile(r"\d+(?:\.\d+)+\Z")
RECORD_TYPES = {"知识点学习", "真题", "案例", "论文素材", "错题复习"}
RESULTS = {"已掌握", "基本掌握", "未掌握", "正确", "错误", "部分完成", "待复习"}
MAX_BODY_BYTES = 32 * 1024
MAX_FIELD_LENGTHS = {
    "title": 200, "source": 240, "result": 32, "error_type": 80, "rule": 800, "tags": 300,
    "prompt_evidence": 1200, "hit_keywords": 600, "missed_keywords": 600, "duration": 40,
    "project_code": 120, "decision": 1200, "tradeoff": 1200, "outcome": 1200, "original_record_id": 80,
}
LOGGER = logging.getLogger(__name__)


def _load_question_bank_module() -> Any:
    """按确定本机文件加载题库模型，不依赖 Python 搜索路径。"""
    path = QUESTION_BANK_ROOT / "题库模型.py"
    spec = importlib.util.spec_from_file_location("local_question_bank_model", path)
    if spec is None or spec.loader is None:
        raise ValueError("无法加载题库数据模型")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_practice_questions(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只加载已核对题目；模型错误应阻止服务带着损坏题库启动。"""
    return _load_question_bank_module().load_verified_questions(QUESTION_BANK_ROOT, points=points)


def load_practice_sources() -> list[dict[str, Any]]:
    """仅加载不含待核对正文或认证信息的来源索引。"""
    return _load_question_bank_module().load_source_index(QUESTION_BANK_ROOT)


def _load_window_json(path: Path, variable: str) -> Any:
    """读取受控站点数据文件中的 `window.<variable> = [...]` JSON。"""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(variable)}\s*=\s*(\[.*\])\s*;?\s*\Z", text, re.S)
    if not match:
        raise ValueError(f"无法读取 {path.name} 中的 window.{variable}")
    return json.loads(match.group(1))


def load_catalog() -> dict[str, dict[str, Any]]:
    """从不公开的台账按 ID 加载白名单；重复 ID 视为配置错误。"""
    records = json.loads(PRIVATE_CATALOG_FILE.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("私有真题台账必须是 JSON 数组")
    catalog: dict[str, dict[str, Any]] = {}
    for record in records:
        question_id = record.get("id") if isinstance(record, dict) else None
        path = record.get("absolute_path") if isinstance(record, dict) else None
        if isinstance(question_id, str) and SAFE_ID.fullmatch(question_id) and isinstance(path, str):
            if question_id in catalog:
                raise ValueError(f"私有真题台账存在重复 ID：{question_id}")
            catalog[question_id] = dict(record)
    return catalog


def load_knowledge() -> list[dict[str, Any]]:
    """加载知识点数据，不从外部真题文件读取任何内容。"""
    records = _load_window_json(KNOWLEDGE_FILE, "KNOWLEDGE_POINT_DATA")
    return [dict(record) for record in records if isinstance(record, dict)]


def question_for_id(catalog: dict[str, dict[str, Any]], question_id: str) -> dict[str, Any] | None:
    """按精确白名单 ID 取登记项，拒绝路径、分隔符和未知 ID。"""
    if not isinstance(question_id, str) or not SAFE_ID.fullmatch(question_id):
        return None
    record = catalog.get(question_id)
    return dict(record) if record else None


def extract_pdf_text(path: Path, max_pages: int = 12, max_chars_per_page: int = 6000) -> str:
    """临时提取有限页数的 PDF 文本；调用方可将依赖异常转为提示。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("未安装 pypdf；请使用 /private/tmp/system-architect-xmind-venv/bin/python 启动服务。") from exc
    try:
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "")[:max_chars_per_page] for page in reader.pages[:max_pages])
    except Exception as exc:  # PDF 可能损坏、加密或不含文字层
        raise RuntimeError(f"PDF 文本提取失败：{exc}") from exc


def _terms(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    value = value.strip()
    if not value:
        return []
    result = [value]
    # 英文缩写、术语和数字编号可单独作为精确命中词。
    result.extend(re.findall(r"[A-Za-z][A-Za-z0-9+._-]{1,}|\d+(?:\.\d+)+", value))
    return list(dict.fromkeys(term for term in result if len(term) >= 2))


def normalize_match_text(value: Any) -> str:
    """归一化用于术语匹配的中英文文本。

    NFKC 合并全角/半角及兼容字形，casefold 统一英文大小写；
    空白、标点和符号不承载术语语义，匹配时忽略。
    """
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if not character.isspace() and unicodedata.category(character)[0] not in {"P", "S"})


def rank_knowledge(question_text: str, points: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """用可解释的精确术语命中，将题干关联到最多 ``limit`` 个知识点。"""
    if not isinstance(question_text, str) or not question_text.strip() or limit <= 0:
        return []
    normalized_question = normalize_match_text(question_text)
    if not normalized_question:
        return []
    matches: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        reasons: list[str] = []
        score = 0

        def score_terms(values: list[str], weight: int) -> None:
            nonlocal score
            for value in values:
                normalized_value = normalize_match_text(value)
                if normalized_value and normalized_value in normalized_question:
                    score += weight
                    if value not in reasons and len(reasons) < 8:
                        reasons.append(value)

        score_terms(_terms(str(point.get("id", ""))), 12)
        score_terms(_terms(point.get("title")), 10)
        tags = point.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                score_terms(_terms(tag), 9)
        score_terms(_terms(point.get("summary")), 2)
        source_paragraphs = point.get("source_paragraphs", [])
        if isinstance(source_paragraphs, list):
            for paragraph in source_paragraphs:
                score_terms(_terms(paragraph), 1)

        if score > 0:
            matches.append({
                "id": point.get("id", ""),
                "title": point.get("title", ""),
                "summary": point.get("summary", ""),
                "reasons": reasons,
                "score": score,
            })
    return sorted(matches, key=lambda item: (-item["score"], str(item["id"])))[:limit]


def markdown_text(value: str) -> str:
    """将用户输入限制为单行 Markdown 文本，避免破坏标题、列表和注释边界。"""
    return value.replace("\r", "").replace("\n", "<br>").replace("<!--", "＜!--").replace("-->", "--＞").strip()


def week_key(value: date) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def _parse_iso_date(value: Any, field: str, required: bool = False) -> str:
    if value in (None, ""):
        if required:
            raise ValueError(f"{field}不能为空")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field}必须是 YYYY-MM-DD 日期")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field}必须是 YYYY-MM-DD 日期") from exc


def _record_id(value: Any) -> str:
    if value in (None, ""):
        return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:4]}"
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}-\d{6}-[a-zA-Z0-9]{4,16}", value):
        raise ValueError("记录 ID 格式不正确")
    return value


def validate_study_record(payload: Any, points: list[dict[str, Any]]) -> dict[str, Any]:
    """校验并规范化学习记录；仅接受预设字段且关联既有知识点。"""
    if not isinstance(payload, dict):
        raise ValueError("记录必须是 JSON 对象")
    allowed = {"id", "type", "knowledge_id", "title", "source", "subject", "result", "error_type", "rule", "review_date", "tags", *MAX_FIELD_LENGTHS}
    unexpected = set(payload) - allowed
    if unexpected:
        raise ValueError(f"存在不支持的字段：{', '.join(sorted(unexpected))}")
    record_type = payload.get("type")
    if record_type not in RECORD_TYPES:
        raise ValueError("记录类型不合法")
    knowledge_id = payload.get("knowledge_id")
    point_map = {str(point.get("id")): point for point in points if isinstance(point, dict)}
    if not isinstance(knowledge_id, str) or not SAFE_KNOWLEDGE_ID.fullmatch(knowledge_id) or knowledge_id not in point_map:
        raise ValueError("关联知识点不存在或格式不正确")
    record: dict[str, Any] = {
        "id": _record_id(payload.get("id")), "type": record_type, "knowledge_id": knowledge_id,
        "knowledge_title": str(point_map[knowledge_id].get("title", "")),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "review_date": _parse_iso_date(payload.get("review_date"), "下次复习日期"),
    }
    for field, limit in MAX_FIELD_LENGTHS.items():
        value = payload.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"{field}必须是文本")
        value = markdown_text(value)
        if len(value) > limit:
            raise ValueError(f"{field}不能超过 {limit} 个字符")
        record[field] = value
    subject = payload.get("subject", "")
    if not isinstance(subject, str):
        raise ValueError("subject必须是文本")
    record["subject"] = markdown_text(subject)[:80]
    if record["result"] and record["result"] not in RESULTS:
        raise ValueError("结果不在允许范围内")
    if not record["title"]:
        record["title"] = record["knowledge_title"]
    return record


def _study_paths(record: dict[str, Any]) -> tuple[Path, Path, str]:
    created = datetime.strptime(record["created_at"], "%Y-%m-%d %H:%M").date()
    key = week_key(created)
    topic_name = f"{record['knowledge_id']}-{record['knowledge_title'].replace('/', '-')}".strip("-")
    return STUDY_ROOT / "周报" / f"{key}.md", STUDY_ROOT / "专题" / f"{topic_name}.md", key


def _ensure_week_file(path: Path, key: str) -> None:
    if path.exists():
        return
    year, week = key.split("-W")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {year} 年第 {int(week)} 周学习档案\n\n## 手工复盘区\n\n"
        "<!-- MANUAL: 本区由学习者填写，程序永不改写。 -->\n\n"
        "## 自动追加记录区\n\n<!-- AUTO-APPEND: 本区仅追加，程序不修改既有内容。 -->\n",
        encoding="utf-8",
    )


def _ensure_topic_file(path: Path, record: dict[str, Any]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {record['knowledge_id']} {record['knowledge_title']}｜学习档案\n\n"
        f"> 对应知识点：`../01-知识点/小节/{record['knowledge_id']}-*.md`\n\n"
        "## 手工笔记区\n\n<!-- MANUAL: 本区由学习者填写，程序永不改写。 -->\n\n"
        "## 追加记录索引\n\n<!-- AUTO-APPEND: 本区仅追加，程序不修改既有内容。 -->\n",
        encoding="utf-8",
    )


def _record_block(record: dict[str, Any]) -> str:
    lines = [
        f"<!-- STUDY-RECORD:{json.dumps(record, ensure_ascii=False, separators=(',', ':'))} -->",
        f"### [{record['id']}] {record['type']}｜{record['knowledge_id']} {record['knowledge_title']}",
        f"- 时间：{record['created_at']}", f"- 标题/题源：{record['title'] or record['source']}",
        f"- 结果：{record['result'] or '未填写'}", f"- 错因：{record['error_type'] or '未填写'}",
        f"- 判断规则：{record['rule'] or '未填写'}", f"- 下次复习：{record['review_date'] or '未安排'}",
        f"- 标签：{record['tags'] or '无'}",
    ]
    details = [("题干依据", record["prompt_evidence"]), ("命中关键词", record["hit_keywords"]),
               ("漏答关键词", record["missed_keywords"]), ("用时", record["duration"]),
               ("项目代号", record["project_code"]), ("关键决策", record["decision"]),
               ("取舍", record["tradeoff"]), ("验证/效果", record["outcome"]),
               ("原记录 ID", record["original_record_id"])]
    present = [(label, value) for label, value in details if value]
    if present:
        lines.extend(["", "#### 完整复盘"])
        lines.extend(f"- {label}：{value}" for label, value in present)
    return "\n".join(lines) + "\n\n"


def append_study_record(record: dict[str, Any], points: list[dict[str, Any]]) -> dict[str, str]:
    """仅追加周报完整记录与专题索引；相同 ID 为幂等提交。"""
    week_path, topic_path, key = _study_paths(record)
    _ensure_week_file(week_path, key)
    _ensure_topic_file(topic_path, record)
    week_name = str(week_path.relative_to(STUDY_ROOT.parent))
    topic_name = str(topic_path.relative_to(STUDY_ROOT.parent))
    existing = week_path.read_text(encoding="utf-8")
    duplicate = f"[{record['id']}]" in existing
    if not duplicate:
        with week_path.open("a", encoding="utf-8") as file:
            file.write(_record_block(record))
    topic_existing = topic_path.read_text(encoding="utf-8")
    if f"[{record['id']}]" not in topic_existing:
        with topic_path.open("a", encoding="utf-8") as file:
            file.write(f"- [{record['id']}] {record['created_at'][:10]}｜{record['type']}｜{record['result'] or '未填写'}｜错因：{record['error_type'] or '未填写'}｜周报：`../周报/{week_path.name}`\n")
    return {"id": record["id"], "week_file": week_name, "topic_file": topic_name, "duplicate": str(duplicate).lower()}


def read_study_records() -> list[dict[str, Any]]:
    """只读取服务写入的单行 JSON 注释，不解释或修改手工 Markdown。"""
    if not STUDY_ROOT.exists():
        return []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted((STUDY_ROOT / "周报").glob("*.md")) if (STUDY_ROOT / "周报").exists() else []:
        for raw in re.findall(r"<!-- STUDY-RECORD:(.*?) -->", path.read_text(encoding="utf-8"), re.S):
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and isinstance(record.get("id"), str) and record["id"] not in seen:
                records.append(record); seen.add(record["id"])
    return sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True)


def study_dashboard(records: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    recent_floor = today - timedelta(days=6)
    due = [item for item in records if item.get("review_date") and item.get("review_date") <= today.isoformat() and item.get("result") != "已掌握"]
    recent = [item for item in records if str(item.get("created_at", ""))[:10] >= recent_floor.isoformat()]
    weak: dict[str, dict[str, Any]] = {}
    for item in records:
        if item.get("result") not in {"错误", "未掌握", "部分完成", "待复习"}:
            continue
        key = str(item.get("knowledge_id", ""))
        bucket = weak.setdefault(key, {"knowledge_id": key, "title": item.get("knowledge_title", ""), "count": 0, "errors": []})
        bucket["count"] += 1
        if item.get("error_type") and item["error_type"] not in bucket["errors"]:
            bucket["errors"].append(item["error_type"])
    return {"due_reviews": due[:12], "recent_records": recent[:12], "weak_topics": sorted(weak.values(), key=lambda item: (-item["count"], item["knowledge_id"]))[:8], "essay_material_count": sum(item.get("type") == "论文素材" for item in records), "record_count": len(records)}


class AppData:
    """启动时一次性载入的受控数据。"""

    def __init__(self, catalog: dict[str, dict[str, Any]], points: list[dict[str, Any]], practice_questions: list[dict[str, Any]] | None = None, practice_sources: list[dict[str, Any]] | None = None) -> None:
        self.catalog = catalog
        self.points = points
        self.practice_questions = practice_questions if practice_questions is not None else []
        self.practice_sources = practice_sources if practice_sources is not None else []
        self.question_match_cache: dict[str, dict[str, Any]] = {}


class LearningRequestHandler(SimpleHTTPRequestHandler):
    """仅开放显式登记的 API，其他路径由受限的 site 根目录静态提供。"""

    app_data: AppData

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(SITE_ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # 保留标准访问日志，避免泄露真题绝对路径。
        super().log_message(format, *args)

    def _json(self, status: int, payload: dict[str, Any], extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError as exc:
            raise ValueError("Content-Length 不合法") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("请求体大小不合法")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("请求体必须是 UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return value

    def _serve_study_dashboard(self) -> None:
        self._json(HTTPStatus.OK, study_dashboard(read_study_records()))

    def _serve_study_records(self, query: dict[str, list[str]]) -> None:
        requested = query.get("knowledge_id", [""])[0]
        if requested and (not SAFE_KNOWLEDGE_ID.fullmatch(requested) or requested not in {str(point.get("id")) for point in self.app_data.points}):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "关联知识点不存在或格式不正确"})
            return
        records = read_study_records()
        if requested:
            records = [record for record in records if record.get("knowledge_id") == requested]
        self._json(HTTPStatus.OK, {"records": records[:50]})

    def _create_study_record(self) -> None:
        try:
            record = validate_study_record(self._read_json_body(), self.app_data.points)
            self._json(HTTPStatus.CREATED, append_study_record(record, self.app_data.points))
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except OSError:
            LOGGER.exception("追加学习档案失败")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "学习档案写入失败，请检查本机目录权限"})

    def _practice_catalog(self) -> None:
        questions = self.app_data.practice_questions
        module = _load_question_bank_module()
        self._json(HTTPStatus.OK, {
            "count": len(questions),
            "types": {key: sum(item.get("type") == key for item in questions) for key in ("single_choice", "case_analysis", "essay")},
            "years": sorted({str(item.get("year", "")) for item in questions if item.get("year")}),
            "subjects": sorted({str(item.get("subject", "")) for item in questions if item.get("subject")}),
            "sources": module.verified_source_catalog(questions),
        })

    def _practice_questions(self, query: dict[str, list[str]]) -> None:
        allowed = {"type", "year", "subject", "knowledge_id", "source_id"}
        if set(query) - allowed or any(len(values) != 1 for values in query.values()):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "题库筛选参数不合法"})
            return
        question_type = query.get("type", [""])[0]
        year = query.get("year", [""])[0]
        subject = query.get("subject", [""])[0]
        knowledge_id = query.get("knowledge_id", [""])[0]
        source_id = query.get("source_id", [""])[0]
        if question_type and question_type not in {"single_choice", "case_analysis", "essay"}:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "题目类型不合法"})
            return
        if year and not re.fullmatch(r"\d{4}|训练", year):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "年份筛选不合法"})
            return
        if knowledge_id and (not SAFE_KNOWLEDGE_ID.fullmatch(knowledge_id) or knowledge_id not in {str(point.get("id")) for point in self.app_data.points}):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "关联知识点不存在或格式不正确"})
            return
        if source_id and not SAFE_PRACTICE_ID.fullmatch(source_id):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "来源筛选不合法"})
            return
        module = _load_question_bank_module()
        questions = module.filter_questions(self.app_data.practice_questions, question_type=question_type, year=year, subject=subject, knowledge_id=knowledge_id, source_id=source_id)[:100]
        summaries = [{key: item[key] for key in ("id", "type", "title", "year", "session", "subject", "knowledge_ids", "source") if key in item} for item in questions]
        self._json(HTTPStatus.OK, {"questions": summaries, "count": len(summaries)})

    def _practice_question(self, question_id: str) -> None:
        if not SAFE_PRACTICE_ID.fullmatch(question_id):
            self._json(HTTPStatus.NOT_FOUND, {"error": "未找到已核对题目"})
            return
        item = _load_question_bank_module().question_by_id(self.app_data.practice_questions, question_id)
        if item is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "未找到已核对题目"})
            return
        self._json(HTTPStatus.OK, {"question": item})

    def _practice_sources(self) -> None:
        self._json(HTTPStatus.OK, {"sources": self.app_data.practice_sources})

    @staticmethod
    def _registered_podcast(chapter: str) -> tuple[dict[str, Any], Path] | None:
        record = PODCAST_CATALOG.get(chapter)
        if record is None or not record["filename"]:
            return None
        root = PODCAST_ROOT.resolve()
        candidate = PODCAST_ROOT / record["filename"]
        try:
            path = candidate.resolve(strict=True)
            path.relative_to(root)
        except (OSError, ValueError):
            return None
        if path.suffix.lower() != ".wav" or not path.is_file():
            return None
        try:
            with path.open("rb") as file:
                header = file.read(12)
        except OSError:
            return None
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            return None
        return record, path

    def _podcast_catalog(self) -> None:
        podcasts = []
        for chapter in sorted(PODCAST_CATALOG, key=int):
            record = PODCAST_CATALOG[chapter]
            podcasts.append({
                "chapter": record["chapter"], "title": record["title"],
                "filename": record["filename"], "duration_seconds": record["duration_seconds"],
                "available": self._registered_podcast(chapter) is not None,
            })
        self._json(HTTPStatus.OK, {"podcasts": podcasts})

    @staticmethod
    def _single_byte_range(value: str, size: int) -> tuple[int, int] | None:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
        if match is None or not any(match.groups()):
            return None
        start_text, end_text = match.groups()
        if not start_text:
            length = int(end_text)
            if length <= 0:
                return None
            return max(0, size - length), size - 1
        start = int(start_text)
        if start >= size:
            return None
        end = int(end_text) if end_text else size - 1
        if end < start:
            return None
        return start, min(end, size - 1)

    def _serve_podcast_audio(self, chapter: str) -> None:
        registered = self._registered_podcast(chapter)
        if registered is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "本机播客文件不可用"})
            return
        _, path = registered
        try:
            with path.open("rb") as file:
                size = os.fstat(file.fileno()).st_size
                requested = self.headers.get("Range")
                byte_range = self._single_byte_range(requested, size) if requested else (0, size - 1)
                if byte_range is None:
                    self._json(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, {"error": "音频范围请求不合法"}, {"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"})
                    return
                start, end = byte_range
                length = end - start + 1
                self.send_response(HTTPStatus.PARTIAL_CONTENT if requested else HTTPStatus.OK)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                if requested:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if self.command != "HEAD":
                    file.seek(start)
                    remaining = length
                    while remaining:
                        chunk = file.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
        except OSError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "本机播客文件不可用"})
        except (BrokenPipeError, ConnectionResetError):
            return

    def _question(self, encoded_id: str) -> tuple[str, dict[str, Any] | None]:
        question_id = unquote(encoded_id)
        return question_id, question_for_id(self.app_data.catalog, question_id)

    @staticmethod
    def _registered_pdf(path: Path) -> bool:
        """只接受存在、扩展名正确且拥有 PDF 文件头的登记文件。"""
        if not path.is_file() or path.suffix.lower() != ".pdf":
            return False
        try:
            with path.open("rb") as file:
                return file.read(5) == b"%PDF-"
        except OSError:
            return False

    def translate_path(self, path: str) -> str:
        """静态文件只能落在 site 根内；解析后也拒绝逃逸的符号链接。"""
        decoded = unquote(urlparse(path).path)
        parts = [part for part in PurePosixPath(decoded).parts if part not in ("/", ".")]
        candidate = SITE_ROOT.joinpath(*parts)
        try:
            candidate.resolve(strict=False).relative_to(SITE_ROOT.resolve())
        except ValueError:
            return str(SITE_ROOT / "__forbidden_path__")
        return str(candidate)

    @staticmethod
    def _metadata(record: dict[str, Any]) -> dict[str, Any]:
        # 不将外部磁盘绝对路径返回给网页。
        allowed = ("id", "year", "session", "subject", "material_type", "title", "status")
        return {key: record[key] for key in allowed if key in record}

    def _serve_question_metadata(self, encoded_id: str) -> None:
        question_id, record = self._question(encoded_id)
        if record is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "未找到已登记的真题 ID"})
            return
        path = Path(record["absolute_path"])
        if not self._registered_pdf(path):
            self._json(HTTPStatus.NOT_FOUND, {"error": "登记的 PDF 文件不存在或不可用"})
            return
        payload = self._metadata(record)
        cached = self.app_data.question_match_cache.get(question_id)
        if cached is not None:
            payload.update(cached)
            self._json(HTTPStatus.OK, payload)
            return
        try:
            question_text = extract_pdf_text(path)
            payload["text_status"] = "已提取前 12 页文字，用于关联知识点。"
            payload["matches"] = rank_knowledge(question_text, self.app_data.points)
        except RuntimeError as exc:
            # 底层库报错可能含有本机绝对路径，仅记录到服务端日志。
            LOGGER.warning("真题 %s 的文本提取不可用：%s", record.get("id", "未知"), exc)
            payload["text_status"] = "暂无法提取题目文字，关联知识点功能不可用；仍可直接预览 PDF。"
            payload["matches"] = []
        self.app_data.question_match_cache[question_id] = {
            "text_status": payload["text_status"],
            "matches": payload["matches"],
        }
        self._json(HTTPStatus.OK, payload)

    def _serve_question_pdf(self, encoded_id: str) -> None:
        _, record = self._question(encoded_id)
        if record is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "未找到已登记的真题 ID"})
            return
        path = Path(record["absolute_path"])
        if not self._registered_pdf(path):
            self._json(HTTPStatus.NOT_FOUND, {"error": "登记的 PDF 文件不存在或不可用"})
            return
        try:
            # 必须先打开、fstat 并验证头部，再承诺 200/PDF 响应。
            with path.open("rb") as file:
                size = os.fstat(file.fileno()).st_size
                if file.read(5) != b"%PDF-":
                    self._json(HTTPStatus.NOT_FOUND, {"error": "登记的文件不是有效 PDF"})
                    return
                file.seek(0)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", "inline")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if self.command != "HEAD":
                    while chunk := file.read(1024 * 1024):
                        self.wfile.write(chunk)
        except OSError:
            # 只会发生在尚未发送 headers 前（open/fstat/read 失败）。
            self._json(HTTPStatus.NOT_FOUND, {"error": "读取登记的 PDF 文件失败"})
        except (BrokenPipeError, ConnectionResetError):
            # headers 已发出后的客户端中断不能改写成 JSON。
            return

    def _handle_api(self) -> bool:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return True
        if path == "/api/study/dashboard":
            self._serve_study_dashboard()
            return True
        if path == "/api/study/records":
            self._serve_study_records(parse_qs(parsed.query, keep_blank_values=True))
            return True
        if path == "/api/practice/catalog":
            self._practice_catalog()
            return True
        if path == "/api/practice/questions":
            self._practice_questions(parse_qs(parsed.query, keep_blank_values=True))
            return True
        if path == "/api/practice/sources":
            self._practice_sources()
            return True
        if path == "/api/podcasts":
            self._podcast_catalog()
            return True
        podcast_match = re.fullmatch(r"/api/podcasts/(\d+)/audio", path)
        if podcast_match:
            self._serve_podcast_audio(podcast_match.group(1))
            return True
        practice_match = re.fullmatch(r"/api/practice/questions/([^/]+)", path)
        if practice_match:
            self._practice_question(unquote(practice_match.group(1)))
            return True
        match = re.fullmatch(r"/api/questions/([^/]+)(/pdf)?", path)
        if match:
            if match.group(2):
                self._serve_question_pdf(match.group(1))
            else:
                self._serve_question_metadata(match.group(1))
            return True
        if path.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "未知接口"})
            return True
        return False

    def do_GET(self) -> None:
        if not self._handle_api():
            super().do_GET()

    def do_HEAD(self) -> None:
        # API 走同一安全路由；静态资源交给父类，避免错误写入响应正文。
        if not self._handle_api():
            super().do_HEAD()

    def do_POST(self) -> None:
        if urlparse(self.path).path == "/api/study/records":
            self._create_study_record()
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "未知接口"})


def make_server(port: int = 8017, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("本地学习服务仅允许监听 127.0.0.1")
    points = load_knowledge()
    LearningRequestHandler.app_data = AppData(load_catalog(), points, load_practice_questions(points), load_practice_sources())
    return ThreadingHTTPServer((host, port), LearningRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="系统架构师知识库本地学习服务")
    parser.add_argument("--port", type=int, default=8017, help="监听端口（默认：8017）")
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"知识库已启动：http://127.0.0.1:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
