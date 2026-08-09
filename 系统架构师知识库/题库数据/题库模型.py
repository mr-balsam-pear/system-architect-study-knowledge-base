"""互动题库的正式题目模型。

本模块只处理人工核对后的静态 JSON，不读取 PDF、网页或私有真题台账。
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any


QUESTION_TYPES = {"single_choice", "case_analysis", "essay"}
QUESTION_ROOT = Path(__file__).resolve().parent
VERIFIED_DIR = QUESTION_ROOT / "已核对"
SOURCE_INDEX_FILE = QUESTION_ROOT / "来源索引" / "外部来源.json"

_QUESTION_ID_RE = re.compile(r"^[A-Za-z0-9:_-]+$")
_OPTION_LABELS = set("ABCDEF")
_COMMON_FIELDS = {
    "id", "type", "status", "title", "year", "session", "subject", "source",
    "knowledge_ids", "stem", "explanation", "review_note",
}
_TYPE_FIELDS = {
    "single_choice": {"options", "answer"},
    "case_analysis": {"material", "questions"},
    "essay": {"prompt", "requirements", "reference_outline"},
}
_SOURCE_FIELDS = {"kind", "source_id", "label", "url"}
_CASE_ITEM_FIELDS = {"id", "prompt", "score", "reference_points"}
_SOURCE_INDEX_FIELDS = {"name", "url", "collected_at", "access", "note", "year", "subject", "question_type"}
_FORBIDDEN_SOURCE_FIELDS = {"body", "stem", "answer", "explanation", "cookie", "token", "signature", "raw_text"}


def _reject_unknown_fields(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label}不允许字段：{', '.join(sorted(unknown))}")


def _required_text(value: Any, label: str, *, maximum: int = 12000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}不能为空")
    if len(value) > maximum:
        raise ValueError(f"{label}不能超过{maximum}个字符")
    return value.strip()


def _text_list(value: Any, label: str, *, minimum: int = 1, maximum: int = 20, item_maximum: int = 3000) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{label}必须包含{minimum}至{maximum}项")
    return [_required_text(item, label, maximum=item_maximum) for item in value]


def _knowledge_ids(value: Any, points: list[dict[str, Any]]) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("关联知识点不能为空")
    known_ids = {item.get("id") for item in points if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if not known_ids:
        raise ValueError("关联知识点目录不可用")
    if len(value) > 12 or any(not isinstance(item, str) or item not in known_ids for item in value):
        raise ValueError("关联知识点不存在或格式不合法")
    if len(value) != len(set(value)):
        raise ValueError("关联知识点不能重复")
    return list(value)


def _source(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("来源必须是对象")
    _reject_unknown_fields(value, _SOURCE_FIELDS, "来源")
    result = {field: _required_text(value.get(field), f"来源.{field}", maximum=300) for field in ("kind", "source_id", "label")}
    url = value.get("url", "")
    if not isinstance(url, str) or len(url) > 2000:
        raise ValueError("来源.url格式不合法")
    if url and not re.fullmatch(r"https?://[^\s]+", url):
        raise ValueError("来源.url必须是公开 HTTP(S) 地址")
    result["url"] = url
    return result


def _common(question: dict[str, Any], points: list[dict[str, Any]]) -> dict[str, Any]:
    question_type = question.get("type")
    if question_type not in QUESTION_TYPES:
        raise ValueError("题目类型不合法")
    allowed = _COMMON_FIELDS | _TYPE_FIELDS[question_type]
    _reject_unknown_fields(question, allowed, "题目")
    question_id = question.get("id")
    if not isinstance(question_id, str) or not _QUESTION_ID_RE.fullmatch(question_id):
        raise ValueError("题目 ID 格式不合法")
    if question.get("status") != "verified":
        raise ValueError("正式题目状态必须为 verified")
    result: dict[str, Any] = {
        "id": question_id,
        "type": question_type,
        "status": "verified",
        "title": _required_text(question.get("title"), "标题", maximum=300),
        "year": _required_text(question.get("year"), "年份", maximum=20),
        "session": _required_text(question.get("session"), "考试批次", maximum=40),
        "subject": _required_text(question.get("subject"), "科目", maximum=100),
        "source": _source(question.get("source")),
        "knowledge_ids": _knowledge_ids(question.get("knowledge_ids"), points),
        "stem": _required_text(question.get("stem"), "题干"),
        "explanation": _required_text(question.get("explanation"), "解析"),
        "review_note": _required_text(question.get("review_note"), "核对说明", maximum=2000),
    }
    return result


def _validate_choice(question: dict[str, Any], result: dict[str, Any]) -> None:
    options = question.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 6:
        raise ValueError("选项必须为 2 至 6 项")
    normalized = []
    labels: list[str] = []
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("选项必须是对象")
        _reject_unknown_fields(option, {"label", "text"}, "选项")
        label = option.get("label")
        if not isinstance(label, str) or label not in _OPTION_LABELS:
            raise ValueError("选项标签必须为 A 至 F")
        labels.append(label)
        normalized.append({"label": label, "text": _required_text(option.get("text"), "选项内容", maximum=3000)})
    if len(labels) != len(set(labels)):
        raise ValueError("选项标签不能重复")
    answer = question.get("answer")
    if not isinstance(answer, str) or answer not in labels:
        raise ValueError("正确答案必须是已有选项")
    result["options"] = normalized
    result["answer"] = answer


def _validate_case(question: dict[str, Any], result: dict[str, Any]) -> None:
    result["material"] = _required_text(question.get("material"), "案例材料")
    items = question.get("questions")
    if not isinstance(items, list) or not items or len(items) > 12:
        raise ValueError("案例分问必须包含 1 至 12 项")
    normalized = []
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("案例分问必须是对象")
        _reject_unknown_fields(item, _CASE_ITEM_FIELDS, "案例分问")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not _QUESTION_ID_RE.fullmatch(item_id):
            raise ValueError("案例分问 ID 格式不合法")
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or score <= 0 or score > 100:
            raise ValueError("案例分问分值不合法")
        ids.append(item_id)
        normalized.append({
            "id": item_id,
            "prompt": _required_text(item.get("prompt"), "案例分问提示"),
            "score": score,
            "reference_points": _text_list(item.get("reference_points"), "案例参考要点", item_maximum=2000),
        })
    if len(ids) != len(set(ids)):
        raise ValueError("案例分问 ID 不能重复")
    result["questions"] = normalized


def _validate_essay(question: dict[str, Any], result: dict[str, Any]) -> None:
    result["prompt"] = _required_text(question.get("prompt"), "论文题目")
    result["requirements"] = _text_list(question.get("requirements"), "论文写作要求", item_maximum=2000)
    result["reference_outline"] = _text_list(question.get("reference_outline"), "论文参考提纲", item_maximum=4000)


def validate_verified_question(question: Any, points: list[dict[str, Any]]) -> dict[str, Any]:
    """校验并返回一份深拷贝、字段固定的正式题目。"""
    if not isinstance(question, dict):
        raise ValueError("题目必须是对象")
    result = _common(question, points)
    if result["type"] == "single_choice":
        _validate_choice(question, result)
    elif result["type"] == "case_analysis":
        _validate_case(question, result)
    else:
        _validate_essay(question, result)
    return deepcopy(result)


def load_verified_questions(root: Path = QUESTION_ROOT, points: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """加载 ``已核对`` 下的数组 JSON；任何损坏数据都会阻止加载。"""
    if points is None:
        raise ValueError("加载正式题库需要知识点目录")
    verified_dir = Path(root) / "已核对"
    if not verified_dir.exists():
        return []
    if not verified_dir.is_dir():
        raise ValueError("已核对目录不可用")
    questions: list[dict[str, Any]] = []
    ids: set[str] = set()
    for path in sorted(verified_dir.glob("*.json")):
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"无法读取正式题库文件：{path.name}") from error
        if not isinstance(entries, list):
            raise ValueError(f"正式题库文件必须是数组：{path.name}")
        for entry in entries:
            item = validate_verified_question(entry, points)
            if item["id"] in ids:
                raise ValueError(f"正式题目 ID 重复：{item['id']}")
            ids.add(item["id"])
            questions.append(item)
    return sorted(questions, key=lambda item: item["id"])


def filter_questions(questions: list[dict[str, Any]], *, question_type: str = "", year: str = "", subject: str = "", knowledge_id: str = "") -> list[dict[str, Any]]:
    """按可选条件筛选题目；返回副本，避免调用方污染加载结果。"""
    if question_type and question_type not in QUESTION_TYPES:
        return []
    selected = [
        item for item in questions
        if (not question_type or item.get("type") == question_type)
        and (not year or item.get("year") == year)
        and (not subject or item.get("subject") == subject)
        and (not knowledge_id or knowledge_id in item.get("knowledge_ids", []))
    ]
    return deepcopy(sorted(selected, key=lambda item: item.get("id", "")))


def question_by_id(questions: list[dict[str, Any]], question_id: str) -> dict[str, Any] | None:
    """按严格 ID 查找单题，拒绝路径形式的输入。"""
    if not isinstance(question_id, str) or not _QUESTION_ID_RE.fullmatch(question_id):
        return None
    for item in questions:
        if item.get("id") == question_id:
            return deepcopy(item)
    return None


def add_source_index(root: Path, payload: Any) -> dict[str, str]:
    """追加受控来源索引；受限页面的正文和认证信息绝不落盘。"""
    if not isinstance(payload, dict):
        raise ValueError("来源索引必须是对象")
    forbidden = set(payload) & _FORBIDDEN_SOURCE_FIELDS
    if forbidden:
        payload = {key: value for key, value in payload.items() if key not in forbidden}
    _reject_unknown_fields(payload, _SOURCE_INDEX_FIELDS, "来源索引")
    name = _required_text(payload.get("name", "未命名来源"), "来源名称", maximum=120)
    url = payload.get("url")
    if not isinstance(url, str) or not re.fullmatch(r"https?://[^\s]+", url):
        raise ValueError("来源索引.url必须是公开 HTTP(S) 地址")
    access = payload.get("access", "public")
    if access not in {"public", "restricted", "unavailable"}:
        raise ValueError("来源索引.access不合法")
    result = {
        "name": name,
        "url": url,
        "collected_at": _required_text(payload.get("collected_at", "未记录"), "采集时间", maximum=40),
        "access": access,
        "note": str(payload.get("note", "")).strip()[:1000],
        "year": str(payload.get("year", "")).strip()[:20],
        "subject": str(payload.get("subject", "")).strip()[:100],
        "question_type": str(payload.get("question_type", "")).strip()[:40],
    }
    path = Path(root) / "来源索引" / "外部来源.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("来源索引文件格式错误") from error
    else:
        entries = []
    if not isinstance(entries, list):
        raise ValueError("来源索引文件必须是数组")
    if result not in entries:
        entries.append(result)
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return deepcopy(result)


def load_source_index(root: Path = QUESTION_ROOT) -> list[dict[str, str]]:
    """读取来源索引，过滤并拒绝泄露性字段。"""
    path = Path(root) / "来源索引" / "外部来源.json"
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("来源索引文件格式错误") from error
    if not isinstance(entries, list):
        raise ValueError("来源索引文件必须是数组")
    result: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("来源索引条目必须是对象")
        result.append(add_source_index_to_memory(entry))
    return deepcopy(result)


def add_source_index_to_memory(payload: dict[str, Any]) -> dict[str, str]:
    """在不写文件的情况下验证来源索引条目，供服务读取使用。"""
    forbidden = set(payload) & _FORBIDDEN_SOURCE_FIELDS
    if forbidden:
        raise ValueError("来源索引不允许保存题目正文或认证信息")
    _reject_unknown_fields(payload, _SOURCE_INDEX_FIELDS, "来源索引")
    url = payload.get("url")
    if not isinstance(url, str) or not re.fullmatch(r"https?://[^\s]+", url):
        raise ValueError("来源索引.url必须是公开 HTTP(S) 地址")
    access = payload.get("access", "public")
    if access not in {"public", "restricted", "unavailable"}:
        raise ValueError("来源索引.access不合法")
    return {
        "name": _required_text(payload.get("name", "未命名来源"), "来源名称", maximum=120),
        "url": url,
        "collected_at": _required_text(payload.get("collected_at", "未记录"), "采集时间", maximum=40),
        "access": access,
        "note": str(payload.get("note", "")).strip()[:1000],
        "year": str(payload.get("year", "")).strip()[:20],
        "subject": str(payload.get("subject", "")).strip()[:100],
        "question_type": str(payload.get("question_type", "")).strip()[:40],
    }
