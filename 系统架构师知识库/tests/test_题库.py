"""正式互动题库数据模型的单元测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
import contextlib
import io


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = KNOWLEDGE_ROOT / "题库数据" / "题库模型.py"
IMPORTER_PATH = KNOWLEDGE_ROOT / "导入题库.py"


def load_question_bank_module():
    spec = importlib.util.spec_from_file_location("question_bank_model", MODEL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_importer_module():
    spec = importlib.util.spec_from_file_location("question_bank_importer", IMPORTER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerifiedQuestionModelTests(unittest.TestCase):
    def setUp(self):
        self.question_bank = load_question_bank_module()
        self.points = [
            {"id": "7.3.4", "title": "以数据为中心的体系结构风格"},
            {"id": "8.1.3", "title": "质量属性场景描述"},
            {"id": "20.3.2", "title": "如何写好正文"},
        ]

    def _source(self):
        return {
            "kind": "self_authored",
            "source_id": "training-set-01",
            "label": "知识库自编训练题",
            "url": "",
        }

    def _choice(self):
        return {
            "id": "training-set-01:choice-01",
            "type": "single_choice",
            "status": "verified",
            "title": "数据中心架构风格辨析",
            "year": "2026",
            "session": "训练",
            "subject": "综合知识",
            "source": self._source(),
            "knowledge_ids": ["7.3.4"],
            "stem": "下列哪项更适合使用黑板体系结构风格？",
            "options": [
                {"label": "A", "text": "固定流程的工资批处理"},
                {"label": "B", "text": "结构化报表的定时导出"},
                {"label": "C", "text": "结合多个知识源的非结构化问题求解"},
                {"label": "D", "text": "单一服务的同步调用"},
            ],
            "answer": "C",
            "explanation": "黑板风格通过共享黑板、知识源和控制机制协同求解复杂问题。",
            "review_note": "自编训练样例；2026-08-08 人工核对。",
        }

    def _case(self):
        return {
            "id": "training-set-01:case-01",
            "type": "case_analysis",
            "status": "verified",
            "title": "质量属性场景与架构取舍",
            "year": "2026",
            "session": "训练",
            "subject": "案例分析",
            "source": self._source(),
            "knowledge_ids": ["7.3.4", "8.1.3"],
            "stem": "根据材料完成架构分析。",
            "material": "某平台需汇总多个异构算法的中间结果，并要求高峰期查询响应时间可度量。",
            "questions": [
                {
                    "id": "q1",
                    "prompt": "写出一个完整的性能质量属性场景。",
                    "score": 8,
                    "reference_points": ["包含刺激源、环境、刺激、响应和响应度量", "给出可量化的响应时间目标"],
                },
                {
                    "id": "q2",
                    "prompt": "说明选择黑板风格时需要关注的一个风险。",
                    "score": 7,
                    "reference_points": ["说明控制机制或共享状态的协调复杂性", "给出监控或隔离的应对措施"],
                },
            ],
            "explanation": "先将质量要求改写为可度量场景，再结合风格机制说明取舍。",
            "review_note": "自编训练样例；2026-08-08 人工核对。",
        }

    def _essay(self):
        return {
            "id": "training-set-01:essay-01",
            "type": "essay",
            "status": "verified",
            "title": "论信息系统架构设计中的质量属性取舍",
            "year": "2026",
            "session": "训练",
            "subject": "论文",
            "source": self._source(),
            "knowledge_ids": ["8.1.3", "20.3.2"],
            "stem": "请围绕你参与的信息系统项目，论述如何进行质量属性取舍。",
            "prompt": "重点说明本人职责、架构决策、实施过程及可验证效果。",
            "requirements": ["交代项目背景、规模和本人角色", "用质量属性场景说明目标", "写出至少一项取舍及验证结果"],
            "reference_outline": ["摘要：项目与核心措施", "正文：背景—问题—决策—实施—效果", "结尾：经验、局限与改进"],
            "explanation": "参考提纲仅用于审题和结构自评，不替代个人项目论述。",
            "review_note": "自编训练样例；2026-08-08 人工核对。",
        }

    def test_load_verified_questions_requires_complete_choice_case_and_essay_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            verified = root / "已核对"
            verified.mkdir()
            (verified / "选择题.json").write_text(json.dumps([self._choice()], ensure_ascii=False), encoding="utf-8")
            (verified / "案例分析.json").write_text(json.dumps([self._case()], ensure_ascii=False), encoding="utf-8")
            (verified / "论文.json").write_text(json.dumps([self._essay()], ensure_ascii=False), encoding="utf-8")
            questions = self.question_bank.load_verified_questions(root, points=self.points)
        self.assertEqual({"single_choice", "case_analysis", "essay"}, {item["type"] for item in questions})
        self.assertEqual(["training-set-01:case-01", "training-set-01:choice-01", "training-set-01:essay-01"], [item["id"] for item in questions])

    def test_verified_question_rejects_unknown_knowledge_and_incomplete_choice_answer(self):
        with self.assertRaisesRegex(ValueError, "关联知识点"):
            self.question_bank.validate_verified_question({**self._choice(), "knowledge_ids": ["../../etc"]}, self.points)
        with self.assertRaisesRegex(ValueError, "正确答案"):
            self.question_bank.validate_verified_question({**self._choice(), "answer": "E"}, self.points)

    def test_rejects_extra_fields_duplicate_options_and_absolute_source_path(self):
        with self.assertRaisesRegex(ValueError, "不允许字段"):
            self.question_bank.validate_verified_question({**self._choice(), "unsafe": True}, self.points)
        duplicate = self._choice()
        duplicate["options"] = [{"label": "A", "text": "一"}, {"label": "A", "text": "二"}]
        with self.assertRaisesRegex(ValueError, "选项"):
            self.question_bank.validate_verified_question(duplicate, self.points)
        source_path = self._choice()
        source_path["source"] = {**self._source(), "url": "/tmp/secret.pdf"}
        with self.assertRaisesRegex(ValueError, "来源"):
            self.question_bank.validate_verified_question(source_path, self.points)

    def test_filter_and_lookup_return_copies(self):
        questions = [
            self.question_bank.validate_verified_question(self._choice(), self.points),
            self.question_bank.validate_verified_question(self._case(), self.points),
            self.question_bank.validate_verified_question(self._essay(), self.points),
        ]
        matched = self.question_bank.filter_questions(questions, question_type="case_analysis", knowledge_id="8.1.3")
        self.assertEqual(["training-set-01:case-01"], [item["id"] for item in matched])
        looked_up = self.question_bank.question_by_id(questions, "training-set-01:choice-01")
        looked_up["title"] = "已修改"
        self.assertEqual("数据中心架构风格辨析", questions[0]["title"])

    def test_filter_supports_source_id_and_catalog_lists_verified_sources(self):
        questions = [
            self.question_bank.validate_verified_question(self._choice(), self.points),
            self.question_bank.validate_verified_question({**self._choice(), "id": "q002:choice-01", "source": {
                "kind": "local_pdf", "source_id": "q002", "label": "2009 真题", "url": "",
            }}, self.points),
        ]
        matched = self.question_bank.filter_questions(questions, source_id="q002")
        self.assertEqual(["q002:choice-01"], [item["id"] for item in matched])
        self.assertEqual(
            ["q002", "training-set-01"],
            [item["source_id"] for item in self.question_bank.verified_source_catalog(questions)],
        )

    def test_explicit_pending_explanation_is_allowed_but_blank_is_rejected(self):
        pending = self.question_bank.validate_verified_question({**self._choice(), "explanation": "待补充"}, self.points)
        self.assertEqual("待补充", pending["explanation"])
        with self.assertRaisesRegex(ValueError, "解析"):
            self.question_bank.validate_verified_question({**self._choice(), "explanation": ""}, self.points)


class ReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.question_bank = load_question_bank_module()
        self.importer = load_importer_module()
        self.catalog = {
            "q002": {
                "id": "q002", "year": "2009", "session": "下半年", "subject": "综合知识",
                "title": "2009 年综合知识", "absolute_path": "/tmp/registered.pdf",
            }
        }

    def test_import_creates_review_batch_without_promoting_questions(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(self.importer, "extract_pdf_text", return_value="(1)A. 甲 B. 乙 C. 丙 D. 丁"):
            root = Path(directory)
            result = self.importer.import_pdf_source("q002", catalog=self.catalog, output_root=root)
            self.assertEqual("needs_review", result["status"])
            self.assertFalse(list((root / "已核对").glob("*.json")))
            batch_path = Path(result["batch_file"])
            batch = json.loads(batch_path.read_text(encoding="utf-8"))
            self.assertIn("raw_text", batch)
            self.assertEqual("q002", batch["source_id"])
            with patch.object(self.importer, "extract_pdf_text", return_value="(2)A. 甲 B. 乙 C. 丙 D. 丁"), patch.object(self.importer, "datetime") as clock:
                clock.now.return_value = datetime(2026, 8, 8, 10, 31, 1)
                second = self.importer.import_pdf_source("q002", catalog=self.catalog, output_root=root)
            self.assertNotEqual(result["batch_file"], second["batch_file"])
            self.assertEqual(2, len(list((root / "待核对").glob("q002-*.json"))))

    def test_restricted_source_index_never_persists_body(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.question_bank.add_source_index(Path(directory), {
                "name": "软考达人", "url": "https://ruankaodaren.com/exam/#/", "collected_at": "2026-08-08",
                "access": "restricted", "note": "仅索引", "body": "forbidden", "token": "forbidden",
            })
            self.assertNotIn("body", record)
            self.assertNotIn("token", record)
            stored = (Path(directory) / "来源索引" / "外部来源.json").read_text(encoding="utf-8")
            self.assertNotIn("forbidden", stored)

    def test_review_template_requires_human_completion_and_promotion_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch_path = root / "待核对" / "q002-20260808-103000.json"
            batch_path.parent.mkdir(parents=True)
            batch_path.write_text(json.dumps({
                "source_id": "q002", "status": "needs_review", "source": {
                    "year": "2009", "session": "下半年", "subject": "综合知识", "title": "2009 真题", "kind": "local_pdf",
                }, "candidates": [{
                    "id": "q002:choice-01", "type": "single_choice", "status": "candidate", "stem": "题干",
                    "options": [{"label": "A", "text": "甲"}, {"label": "B", "text": "乙"}],
                    "answer_candidate": "A", "explanation_candidate": "", "warnings": ["必须人工核对"],
                }], "warnings": [],
            }, ensure_ascii=False), encoding="utf-8")
            review_path = self.importer.create_review_file(batch_path, output_root=root)
            draft = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual("review_required", draft["status"])
            with self.assertRaisesRegex(ValueError, "人工核对"):
                self.importer.promote_review_file(review_path, points=self.question_bank and self._points(), output_root=root)

            draft.update({
                "status": "verified", "title": "第 1 题", "knowledge_ids": ["7.3.4"], "answer": "A",
                "explanation": "待补充", "review_note": "2026-08-12 人工对照原 PDF 核对题干、选项和答案。",
            })
            review_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            result = self.importer.promote_review_file(review_path, points=self._points(), output_root=root)
            self.assertEqual("q002:choice-01", result["id"])
            with self.assertRaisesRegex(ValueError, "已存在"):
                self.importer.promote_review_file(review_path, points=self._points(), output_root=root)

    def test_cli_review_action_dispatches_without_promoting(self):
        output = io.StringIO()
        # 用 os-native 的路径断言：Windows 上 str(Path(...)) 是反斜杠形式。
        review_path = Path("/tmp/review.json")
        with patch.object(sys, "argv", ["导入题库.py", "--action", "review", "--batch-file", "/tmp/batch.json", "--candidate-id", "q002:choice-01"]), patch.object(
            self.importer, "create_review_file", return_value=review_path
        ) as create, contextlib.redirect_stdout(output):
            self.importer.main()
        create.assert_called_once_with(Path("/tmp/batch.json"), candidate_id="q002:choice-01")
        self.assertIn(str(review_path), output.getvalue())

    @staticmethod
    def _points():
        return [{"id": "7.3.4", "title": "以数据为中心的体系结构风格"}]


class GitIgnoreBoundaryTests(unittest.TestCase):
    """锁定公开仓库边界：待核对层必须整目录忽略，已核对层必须保持跟踪。

    回归背景：``待核对/*.json`` 只匹配一层，导致
    ``待核对/外部题库/xxx.json`` 这类子目录下的第三方题目正文会被 git 看到。
    """

    def setUp(self):
        self.repo_root = KNOWLEDGE_ROOT.parent
        self.gitignore = self.repo_root / ".gitignore"
        self.assertTrue(self.gitignore.is_file(), "缺少 .gitignore")

    def _patterns(self) -> list[str]:
        return [
            line.strip()
            for line in self.gitignore.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def test_review_queue_is_ignored_at_every_depth(self):
        patterns = self._patterns()
        self.assertTrue(
            any(pattern.rstrip("/") == "系统架构师知识库/题库数据/待核对" for pattern in patterns),
            "待核对目录必须整体忽略，避免子目录下的第三方题目正文进入公开仓库",
        )

    def test_verified_bank_is_not_ignored(self):
        for pattern in self._patterns():
            self.assertNotIn(
                "已核对", pattern,
                f"已核对题库不能被忽略：{pattern}",
            )

    def test_gitignore_covers_review_queue_subdirectories(self):
        """用真实的 git 判定，确认待核对层的多级子目录都在忽略范围内。"""
        if shutil.which("git") is None:
            self.skipTest("环境缺少 git")
        samples = [
            "系统架构师知识库/题库数据/待核对/q001-20260101-000000.json",
            "系统架构师知识库/题库数据/待核对/外部题库/external.json",
            "系统架构师知识库/题库数据/待核对/人工核对/draft.json",
            "系统架构师知识库/题库数据/待核对/导入批次台账.json",
        ]
        for sample in samples:
            result = subprocess.run(
                ["git", "check-ignore", "-q", sample],
                cwd=self.repo_root, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, f"未被忽略，存在泄漏风险：{sample}")


if __name__ == "__main__":
    unittest.main()
