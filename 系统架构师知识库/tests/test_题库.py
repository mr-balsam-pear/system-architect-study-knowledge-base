"""正式互动题库数据模型的单元测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


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
            batch = json.loads((root / "待核对" / "q002.json").read_text(encoding="utf-8"))
            self.assertIn("raw_text", batch)
            self.assertEqual("q002", batch["source_id"])
            with self.assertRaisesRegex(ValueError, "已存在"):
                self.importer.import_pdf_source("q002", catalog=self.catalog, output_root=root)

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


if __name__ == "__main__":
    unittest.main()
