"""本地学习服务的安全边界、数据加载与关联规则测试。

测试仅使用内存和临时文件；绝不打开外部真题目录中的 PDF。
"""

from __future__ import annotations

import contextlib
from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = KNOWLEDGE_ROOT / "本地学习服务.py"
LAUNCHER_PATH = KNOWLEDGE_ROOT / "启动知识库.py"


def load_module(path: Path, name: str):
    """避免中文文件名不能用普通 import 的限制。"""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_service_module():
    return load_module(SERVICE_PATH, "local_study_service")


class _UnclosableBytesIO(io.BytesIO):
    def close(self):  # HTTP handler 收尾时仍可读取响应。
        pass


class _FakeSocket:
    def __init__(self, request: bytes):
        self.input = io.BytesIO(request)
        self.output = _UnclosableBytesIO()

    def makefile(self, mode, _buffer_size=-1):
        return self.input if "r" in mode else self.output

    def sendall(self, data):
        self.output.write(data)


class _DisconnectingSocket(_FakeSocket):
    """在响应头写出后模拟浏览器取消音频请求。"""

    def __init__(self, request: bytes):
        super().__init__(request)
        self.send_count = 0

    def sendall(self, data):
        self.send_count += 1
        if self.send_count > 1:
            raise BrokenPipeError("client disconnected")
        super().sendall(data)


class _FakeServer:
    server_version = "TestHTTP"
    sys_version = ""


def handle_http(service, target: str, catalog, points=(), method="GET", practice_questions=None, practice_sources=None, request_headers=None):
    """在无监听端口的单测环境下执行一次真实 HTTP handler 请求。"""
    service.LearningRequestHandler.app_data = service.AppData(catalog, list(points), practice_questions, practice_sources)
    headers = {"Host": "localhost", **(request_headers or {})}
    raw_headers = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
    socket = _FakeSocket(f"{method} {target} HTTP/1.1\r\n{raw_headers}\r\n".encode())
    service.LearningRequestHandler(socket, ("127.0.0.1", 0), _FakeServer())
    raw = socket.output.getvalue()
    header, body = raw.split(b"\r\n\r\n", 1)
    status = int(header.splitlines()[0].split()[1])
    return status, header.decode("iso-8859-1"), body


class DataLoadingTests(unittest.TestCase):
    def test_load_private_catalog_and_knowledge_data(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_catalog = root / "private.json"
            points = root / "knowledge-data.js"
            private_catalog.write_text('[{"id":"q001","absolute_path":"/tmp/a.pdf"}]', encoding="utf-8")
            points.write_text(
                'window.KNOWLEDGE_POINT_DATA = [{"id":"8.3","title":"ATAM"}, "bad"];', encoding="utf-8"
            )
            with patch.object(service, "PRIVATE_CATALOG_FILE", private_catalog), patch.object(service, "KNOWLEDGE_FILE", points):
                self.assertEqual(["q001"], list(service.load_catalog()))
                self.assertEqual([{"id": "8.3", "title": "ATAM"}], service.load_knowledge())

    def test_private_catalog_rejects_duplicate_ids(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            private_catalog = Path(directory) / "private.json"
            private_catalog.write_text('[{"id":"q001","absolute_path":"/tmp/a.pdf"},{"id":"q001","absolute_path":"/tmp/b.pdf"}]', encoding="utf-8")
            with patch.object(service, "PRIVATE_CATALOG_FILE", private_catalog):
                with self.assertRaisesRegex(ValueError, "重复 ID"):
                    service.load_catalog()

    def test_public_data_does_not_expose_absolute_path(self):
        public_data = (KNOWLEDGE_ROOT / "site" / "data.js").read_text(encoding="utf-8")
        self.assertNotIn("absolute_path", public_data)


class QuestionLookupTests(unittest.TestCase):
    def test_question_id_does_not_accept_paths(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            catalog = {"q001": {"absolute_path": str(Path(directory) / "safe.pdf")}}
            self.assertTrue(service.question_for_id(catalog, "q001")["absolute_path"].endswith("safe.pdf"))
            self.assertIsNone(service.question_for_id(catalog, "../../etc/passwd"))
            self.assertIsNone(service.question_for_id(catalog, "q001/pdf"))
            self.assertIsNone(service.question_for_id(catalog, "unknown"))


class PdfExtractionTests(unittest.TestCase):
    def test_extract_pdf_text_limits_page_count_and_characters(self):
        service = load_service_module()

        class Page:
            def __init__(self, text):
                self.text = text

            def extract_text(self):
                return self.text

        class Reader:
            def __init__(self, _path):
                self.pages = [Page("abcdef"), Page("ghijkl"), Page("not-read")]

        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = Reader
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            result = service.extract_pdf_text(Path("/temporary/only.pdf"), max_pages=2, max_chars_per_page=3)
        self.assertEqual("abc\n\nghi", result)

    def test_extract_pdf_text_explains_missing_pypdf(self):
        service = load_service_module()
        with patch.dict(sys.modules, {"pypdf": None}):
            with self.assertRaisesRegex(RuntimeError, "未安装 pypdf"):
                service.extract_pdf_text(Path("/temporary/only.pdf"))


class KnowledgeRankingTests(unittest.TestCase):
    def test_rank_knowledge_returns_explainable_matches(self):
        service = load_service_module()
        points = [{"id": "8.3", "title": "ATAM 方法架构评估实践", "tags": ["ATAM", "架构评估"], "summary": "ATAM 分阶段评估"}]
        matches = service.rank_knowledge("使用 ATAM 方法进行架构评估", points)
        self.assertEqual("8.3", matches[0]["id"])
        self.assertIn("ATAM", matches[0]["reasons"])
        self.assertGreater(matches[0]["score"], 0)
        self.assertLessEqual(len(matches[0]["reasons"]), 8)

    def test_rank_knowledge_only_returns_positive_actual_matches(self):
        service = load_service_module()
        points = [{"id": "1.1", "title": "系统概述", "tags": ["系统"], "summary": "基础"}, {"id": "9.2", "title": "无关主题", "tags": ["云计算"], "summary": "无命中"}]
        matches = service.rank_knowledge("系统设计", points)
        self.assertEqual(["1.1"], [match["id"] for match in matches])
        self.assertEqual(["系统"], matches[0]["reasons"])

    def test_rank_knowledge_normalizes_width_case_spacing_and_punctuation(self):
        service = load_service_module()
        points = [{"id": "8.3", "title": "ATAM 架构评估", "tags": [], "summary": ""}]
        matches = service.rank_knowledge("ａｔａｍ，架 构。评估", points)
        self.assertEqual(["8.3"], [match["id"] for match in matches])
        self.assertIn("ATAM 架构评估", matches[0]["reasons"])

    def test_rank_knowledge_matches_source_paragraphs(self):
        service = load_service_module()
        points = [{
            "id": "7.3.4", "title": "无关标题", "tags": [], "summary": "无关摘要",
            "source_paragraphs": ["黑板系统通过知识源协同求解复杂问题。"],
        }]
        matches = service.rank_knowledge("黑板系统，通过知识源协同求解复杂问题", points)
        self.assertEqual(["7.3.4"], [match["id"] for match in matches])
        self.assertIn("黑板系统通过知识源协同求解复杂问题。", matches[0]["reasons"])


class StudyArchiveTests(unittest.TestCase):
    def _points(self):
        return [{"id": "7.3.4", "title": "以数据为中心的体系结构风格"}]

    def _payload(self, **changes):
        payload = {"id": "20260808-103000-a1b2", "type": "真题", "knowledge_id": "7.3.4", "title": "2022 下午案例", "result": "未掌握", "error_type": "概念混淆", "rule": "仓库与黑板的适用场景不同。", "review_date": "2026-08-11", "tags": "架构风格"}
        payload.update(changes)
        return payload

    def test_append_creates_week_and_topic_without_overwriting_manual_notes(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "STUDY_ROOT", Path(directory) / "学习档案"):
            record = service.validate_study_record(self._payload(), self._points())
            first = service.append_study_record(record, self._points())
            week = service.STUDY_ROOT.parent / first["week_file"]
            topic = next((service.STUDY_ROOT / "专题").glob("7.3.4-*.md"))
            week.write_text(week.read_text(encoding="utf-8") + "\n我的手工复盘不可覆盖\n", encoding="utf-8")
            again = service.append_study_record(record, self._points())
            self.assertEqual("true", again["duplicate"])
            self.assertEqual(1, week.read_text(encoding="utf-8").count("[20260808-103000-a1b2]"))
            self.assertIn("我的手工复盘不可覆盖", week.read_text(encoding="utf-8"))
            self.assertLess(week.read_text(encoding="utf-8").index("## 手工复盘区"), week.read_text(encoding="utf-8").index("## 自动追加记录区"))
            self.assertIn("[20260808-103000-a1b2]", topic.read_text(encoding="utf-8"))

    def test_duplicate_week_record_repairs_missing_topic_index(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "STUDY_ROOT", Path(directory) / "学习档案"):
            record = service.validate_study_record(self._payload(), self._points())
            first = service.append_study_record(record, self._points())
            week = service.STUDY_ROOT.parent / first["week_file"]
            topic = service.STUDY_ROOT.parent / first["topic_file"]
            topic.write_text(topic.read_text(encoding="utf-8").replace(
                next(line for line in topic.read_text(encoding="utf-8").splitlines() if "[20260808-103000-a1b2]" in line) + "\n", ""
            ), encoding="utf-8")

            again = service.append_study_record(record, self._points())

            self.assertEqual("true", again["duplicate"])
            self.assertEqual(1, week.read_text(encoding="utf-8").count("[20260808-103000-a1b2]"))
            self.assertEqual(1, topic.read_text(encoding="utf-8").count("[20260808-103000-a1b2]"))

    def test_validation_rejects_unknown_path_type_and_oversized_fields(self):
        service = load_service_module()
        with self.assertRaisesRegex(ValueError, "关联知识点"):
            service.validate_study_record(self._payload(knowledge_id="../../etc/passwd"), self._points())
        with self.assertRaisesRegex(ValueError, "记录类型"):
            service.validate_study_record(self._payload(type="任意文件"), self._points())
        with self.assertRaisesRegex(ValueError, "title不能超过"):
            service.validate_study_record(self._payload(title="x" * 201), self._points())

    def test_dashboard_returns_due_recent_weak_and_essay_counts(self):
        service = load_service_module()
        records = [
            {"id": "a", "created_at": "2026-08-08 10:00", "review_date": "2026-08-08", "result": "未掌握", "knowledge_id": "7.3.4", "knowledge_title": "架构风格", "error_type": "概念混淆", "type": "真题"},
            {"id": "b", "created_at": "2026-08-07 10:00", "review_date": "", "result": "基本掌握", "knowledge_id": "7.3.4", "knowledge_title": "架构风格", "error_type": "", "type": "论文素材"},
        ]
        dashboard = service.study_dashboard(records, date.fromisoformat("2026-08-08"))
        self.assertEqual(["a"], [item["id"] for item in dashboard["due_reviews"]])
        self.assertEqual("7.3.4", dashboard["weak_topics"][0]["knowledge_id"])
        self.assertEqual(1, dashboard["essay_material_count"])


class HttpHandlerTests(unittest.TestCase):
    def _practice_question(self):
        return {
            "id": "training-set-01:choice-01", "type": "single_choice", "status": "verified",
            "title": "训练选择题", "year": "2026", "session": "训练", "subject": "综合知识",
            "source": {"kind": "self_authored", "source_id": "training-set-01", "label": "自编", "url": ""},
            "knowledge_ids": ["7.3.4"], "stem": "下列哪项正确？",
            "options": [{"label": "A", "text": "甲"}, {"label": "B", "text": "乙"}],
            "answer": "A", "explanation": "解析", "review_note": "人工核对",
        }

    def test_health_and_unknown_id_are_json(self):
        service = load_service_module()
        status, headers, body = handle_http(service, "/health", {})
        self.assertEqual(200, status)
        self.assertIn("application/json", headers)
        self.assertEqual({"status": "ok"}, json.loads(body))
        status, _, body = handle_http(service, "/api/questions/not-registered", {})
        self.assertEqual(404, status)
        self.assertIn("未找到已登记", json.loads(body)["error"])

    def test_encoded_path_traversal_is_rejected(self):
        service = load_service_module()
        status, _, body = handle_http(service, "/api/questions/%2E%2E%2Fetc%2Fpasswd", {"q001": {"absolute_path": "/tmp/never.pdf"}})
        self.assertEqual(404, status)
        self.assertIn("未找到已登记", json.loads(body)["error"])

    def test_controlled_pdf_only_streams_registered_temp_file(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            safe_pdf = Path(directory) / "safe.pdf"
            safe_pdf.write_bytes(b"%PDF-test-bytes")
            catalog = {"q001": {"id": "q001", "title": "临时真题", "absolute_path": str(safe_pdf)}}
            status, headers, body = handle_http(service, "/api/questions/q001/pdf", catalog)
        self.assertEqual(200, status)
        self.assertIn("Content-Type: application/pdf", headers)
        self.assertEqual(b"%PDF-test-bytes", body)

    def test_non_pdf_header_is_not_streamed_as_pdf(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            fake_pdf = Path(directory) / "safe.pdf"
            fake_pdf.write_bytes(b"not-a-pdf")
            status, headers, body = handle_http(service, "/api/questions/q001/pdf", {"q001": {"absolute_path": str(fake_pdf)}})
        self.assertEqual(404, status)
        self.assertIn("application/json", headers)
        self.assertIn("PDF", json.loads(body)["error"])

    def test_metadata_does_not_leak_pdf_extraction_exception_details(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            safe_pdf = Path(directory) / "safe.pdf"
            safe_pdf.write_bytes(b"%PDF-minimal")
            catalog = {"q001": {"id": "q001", "absolute_path": str(safe_pdf)}}
            with patch.object(service, "extract_pdf_text", side_effect=RuntimeError("cannot open /secret/path.pdf")):
                status, _, body = handle_http(service, "/api/questions/q001", catalog)
        payload = json.loads(body)
        self.assertEqual(200, status)
        self.assertEqual([], payload["matches"])
        self.assertIn("暂无法提取", payload["text_status"])
        self.assertNotIn("/secret/path.pdf", body.decode("utf-8"))

    def test_question_metadata_caches_extraction_and_matches_by_question_id(self):
        service = load_service_module()
        points = [{"id": "8.3", "title": "ATAM", "tags": [], "summary": ""}]
        with tempfile.TemporaryDirectory() as directory:
            safe_pdf = Path(directory) / "safe.pdf"
            safe_pdf.write_bytes(b"%PDF-minimal")
            catalog = {"q001": {"id": "q001", "absolute_path": str(safe_pdf)}}
            service.LearningRequestHandler.app_data = service.AppData(catalog, points)
            with patch.object(service, "extract_pdf_text", return_value="ATAM") as extract:
                for _ in range(2):
                    socket = _FakeSocket(b"GET /api/questions/q001 HTTP/1.1\r\nHost: localhost\r\n\r\n")
                    service.LearningRequestHandler(socket, ("127.0.0.1", 0), _FakeServer())
                    self.assertEqual(200, int(socket.output.getvalue().split(b"\r\n", 1)[0].split()[1]))
            self.assertEqual(1, extract.call_count)

    def test_static_directory_traversal_is_not_served(self):
        service = load_service_module()
        status, _, _ = handle_http(service, "/%2e%2e/%2e%2e/etc/passwd", {})
        self.assertEqual(404, status)

    def test_static_symlink_to_outside_site_is_not_served(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            link = service.SITE_ROOT / "test-outside-link"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("当前平台不支持创建符号链接")
            try:
                status, _, body = handle_http(service, "/test-outside-link", {})
                self.assertEqual(404, status)
                self.assertNotIn(b"secret", body)
            finally:
                link.unlink(missing_ok=True)

    def test_head_for_static_resource_has_no_body(self):
        service = load_service_module()
        status, _, body = handle_http(service, "/data.js", {}, method="HEAD")
        self.assertEqual(200, status)
        self.assertEqual(b"", body)

    def test_service_rejects_non_loopback_host(self):
        service = load_service_module()
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            service.make_server(0, host="0.0.0.0")

    def test_study_routes_validate_and_return_dashboard(self):
        service = load_service_module()
        points = [{"id": "7.3.4", "title": "以数据为中心的体系结构风格"}]
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "STUDY_ROOT", Path(directory) / "学习档案"):
            payload = {"id": "20260808-103000-a1b2", "type": "知识点学习", "knowledge_id": "7.3.4", "result": "未掌握", "review_date": "2026-08-08"}
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = b"POST /api/study/records HTTP/1.1\r\nHost: localhost\r\nContent-Length: " + str(len(raw)).encode() + b"\r\n\r\n" + raw
            service.LearningRequestHandler.app_data = service.AppData({}, points)
            socket = _FakeSocket(request)
            service.LearningRequestHandler(socket, ("127.0.0.1", 0), _FakeServer())
            status = int(socket.output.getvalue().split(b"\r\n", 1)[0].split()[1])
            self.assertEqual(201, status)
            status, _, body = handle_http(service, "/api/study/dashboard", {}, points)
            self.assertEqual(200, status)
            self.assertEqual(1, json.loads(body)["record_count"])

            status, _, body = handle_http(service, "/api/study/records?knowledge_id=7.3.4", {}, points)
            self.assertEqual(200, status)
            self.assertEqual(["20260808-103000-a1b2"], [item["id"] for item in json.loads(body)["records"]])
            status, _, body = handle_http(service, "/api/study/records?knowledge_id=../../etc", {}, points)
            self.assertEqual(400, status)
            self.assertIn("关联知识点", json.loads(body)["error"])

    def test_practice_routes_filter_securely_and_hide_review_content(self):
        service = load_service_module()
        points = [{"id": "7.3.4", "title": "以数据为中心的体系结构风格"}]
        question = self._practice_question()
        sources = [{"name": "软考达人", "url": "https://ruankaodaren.com/exam/#/", "collected_at": "2026-08-08", "access": "restricted", "note": "仅索引", "year": "", "subject": "", "question_type": ""}]
        status, _, body = handle_http(service, "/api/practice/questions?type=single_choice&knowledge_id=7.3.4", {}, points, practice_questions=[question], practice_sources=sources)
        self.assertEqual(200, status)
        self.assertEqual(["training-set-01:choice-01"], [item["id"] for item in json.loads(body)["questions"]])
        status, _, body = handle_http(service, "/api/practice/questions/..%2Fsecret", {}, points, practice_questions=[question], practice_sources=sources)
        self.assertEqual(404, status)
        status, _, body = handle_http(service, "/api/practice/sources", {}, points, practice_questions=[question], practice_sources=sources)
        self.assertEqual(200, status)
        self.assertNotIn("raw_text", body.decode("utf-8"))

    def test_practice_catalog_and_filter_include_verified_sources(self):
        service = load_service_module()
        points = [{"id": "7.3.4", "title": "以数据为中心的体系结构风格"}]
        question = self._practice_question()
        status, _, body = handle_http(service, "/api/practice/catalog", {}, points, practice_questions=[question])
        self.assertEqual(200, status)
        catalog = json.loads(body)
        self.assertEqual(["training-set-01"], [item["source_id"] for item in catalog["sources"]])
        status, _, body = handle_http(
            service, "/api/practice/questions?source_id=training-set-01", {}, points, practice_questions=[question]
        )
        self.assertEqual(200, status)
        self.assertEqual(["training-set-01:choice-01"], [item["id"] for item in json.loads(body)["questions"]])
        status, _, _ = handle_http(service, "/api/practice/questions?source_id=../../etc", {}, points, practice_questions=[question])
        self.assertEqual(400, status)


class PodcastHttpTests(unittest.TestCase):
    WAV_BYTES = b"RIFF" + (28).to_bytes(4, "little") + b"WAVEfmt " + b"test-audio-bytes"

    def _write_registered_audio(self, service, root: Path, chapter: str = "2") -> Path:
        root.mkdir(parents=True, exist_ok=True)
        path = root / service.PODCAST_CATALOG[chapter]["filename"]
        path.write_bytes(self.WAV_BYTES)
        return path

    def test_podcast_catalog_returns_twenty_safe_entries_and_availability(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "PODCAST_ROOT", Path(directory)):
            self._write_registered_audio(service, Path(directory), "2")
            status, _, body = handle_http(service, "/api/podcasts", {})
        payload = json.loads(body)
        self.assertEqual(200, status)
        self.assertEqual(20, len(payload["podcasts"]))
        self.assertEqual({"chapter", "title", "filename", "duration_seconds", "available"}, set(payload["podcasts"][0]))
        self.assertFalse(next(item for item in payload["podcasts"] if item["chapter"] == "1")["available"])
        self.assertTrue(next(item for item in payload["podcasts"] if item["chapter"] == "2")["available"])
        self.assertFalse(next(item for item in payload["podcasts"] if item["chapter"] == "4")["available"])
        self.assertNotIn(str(Path(directory)), body.decode("utf-8"))

    def test_podcast_audio_supports_full_and_single_ranges(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "PODCAST_ROOT", Path(directory)):
            self._write_registered_audio(service, Path(directory))
            status, headers, body = handle_http(service, "/api/podcasts/2/audio", {})
            self.assertEqual(200, status)
            self.assertIn("Content-Type: audio/wav", headers)
            self.assertIn("Accept-Ranges: bytes", headers)
            self.assertEqual(self.WAV_BYTES, body)

            status, headers, body = handle_http(service, "/api/podcasts/2/audio", {}, request_headers={"Range": "bytes=4-11"})
            self.assertEqual(206, status)
            self.assertIn(f"Content-Range: bytes 4-11/{len(self.WAV_BYTES)}", headers)
            self.assertEqual(self.WAV_BYTES[4:12], body)

            status, headers, body = handle_http(service, "/api/podcasts/2/audio", {}, request_headers={"Range": "bytes=-5"})
            self.assertEqual(206, status)
            self.assertEqual(self.WAV_BYTES[-5:], body)

            status, _, body = handle_http(service, "/api/podcasts/2/audio", {}, request_headers={"Range": "bytes=10-"})
            self.assertEqual(206, status)
            self.assertEqual(self.WAV_BYTES[10:], body)

    def test_podcast_audio_ignores_client_disconnect_after_headers(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "PODCAST_ROOT", Path(directory)):
            self._write_registered_audio(service, Path(directory))
            service.LearningRequestHandler.app_data = service.AppData({}, [])
            request = b"GET /api/podcasts/2/audio HTTP/1.1\r\nHost: localhost\r\n\r\n"
            socket = _DisconnectingSocket(request)
            service.LearningRequestHandler(socket, ("127.0.0.1", 0), _FakeServer())

        self.assertGreater(socket.send_count, 1)

    def test_podcast_audio_rejects_invalid_ranges_with_416(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "PODCAST_ROOT", Path(directory)):
            self._write_registered_audio(service, Path(directory))
            for value in ("bytes=999-1000", "bytes=8-4", "items=0-2", "bytes=0-1,4-5", "bytes=-0"):
                status, headers, body = handle_http(service, "/api/podcasts/2/audio", {}, request_headers={"Range": value})
                self.assertEqual(416, status, value)
                self.assertIn(f"Content-Range: bytes */{len(self.WAV_BYTES)}", headers)
                self.assertIn("application/json", headers)
                self.assertIn("error", json.loads(body))

    def test_podcast_audio_rejects_unknown_traversal_missing_and_invalid_files_safely(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "PODCAST_ROOT", Path(directory)):
            root = Path(directory)
            root.mkdir(exist_ok=True)
            for target in ("/api/podcasts/99/audio", "/api/podcasts/%2E%2E%2F2/audio", "/api/podcasts/1/audio", "/api/podcasts/2/audio"):
                status, headers, body = handle_http(service, target, {})
                self.assertEqual(404, status, target)
                self.assertIn("application/json", headers)
                self.assertNotIn(str(root), body.decode("utf-8"))

            audio = self._write_registered_audio(service, root)
            audio.write_bytes(b"not-a-wave")
            status, _, body = handle_http(service, "/api/podcasts/2/audio", {})
            self.assertEqual(404, status)
            self.assertNotIn(str(root), body.decode("utf-8"))

            audio.unlink()
            outside = root.parent / "outside.wav"
            outside.write_bytes(self.WAV_BYTES)
            try:
                audio.symlink_to(outside)
                status, _, body = handle_http(service, "/api/podcasts/2/audio", {})
                self.assertEqual(404, status)
                self.assertNotIn(str(outside), body.decode("utf-8"))
            finally:
                outside.unlink(missing_ok=True)

    def test_podcast_audio_rejects_bad_extension_and_catalog_path_escape(self):
        service = load_service_module()
        with tempfile.TemporaryDirectory() as directory, patch.object(service, "PODCAST_ROOT", Path(directory)):
            root = Path(directory)
            (root / "audio.txt").write_bytes(self.WAV_BYTES)
            bad_extension = {**service.PODCAST_CATALOG["2"], "filename": "audio.txt"}
            with patch.dict(service.PODCAST_CATALOG, {"2": bad_extension}):
                status, _, body = handle_http(service, "/api/podcasts/2/audio", {})
            self.assertEqual(404, status)

            outside = root.parent / "escaped.wav"
            outside.write_bytes(self.WAV_BYTES)
            try:
                escaped = {**service.PODCAST_CATALOG["2"], "filename": "../escaped.wav"}
                with patch.dict(service.PODCAST_CATALOG, {"2": escaped}):
                    status, _, body = handle_http(service, "/api/podcasts/2/audio", {})
                self.assertEqual(404, status)
                self.assertNotIn(str(outside), body.decode("utf-8"))
            finally:
                outside.unlink(missing_ok=True)


class LauncherTests(unittest.TestCase):
    def test_launcher_warns_but_starts_when_pypdf_missing(self):
        launcher = load_module(LAUNCHER_PATH, "knowledge_launcher")
        output = io.StringIO()
        with patch.dict(sys.modules, {"pypdf": None}), patch("subprocess.run") as run, contextlib.redirect_stdout(output):
            launcher.main()
        self.assertTrue(run.called)
        self.assertIn("缺少 pypdf", output.getvalue())
        command = run.call_args.args[0]
        self.assertEqual(sys.executable, command[0])
        self.assertNotIn("--host", command)


if __name__ == "__main__":
    unittest.main()
