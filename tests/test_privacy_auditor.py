"""
privacy_auditor.py 测试 — 验证隐私审计扫描、修复和报告生成行为。

测试说明：
- 所有 _llm_scrub() 调用均使用 mock，不进行真实 API 请求
- 使用 tmp_path 构建隔离的 twins 目录结构
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数：构建测试用 knowledge JSON 文件
# ─────────────────────────────────────────────────────────────────────────────

def _make_knowledge_file(
    context_dir: Path,
    filename: str,
    chunks: list[dict],
    source_type: str = "wechat_csv",
    context_label: str = "partner",
    twin_slug: str = "test-twin",
) -> Path:
    """在 context_dir 下写入一个合法的 ingestion JSON 文件。"""
    context_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": "1.0",
        "source_type": source_type,
        "context_label": context_label,
        "twin_slug": twin_slug,
        "imported_at": "2026-04-05T00:00:00+00:00",
        "source_file": "test.csv",
        "scrub_stats": {},
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    path = context_dir / filename
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _make_twin_structure(base_dir: Path, slug: str = "test-twin") -> Path:
    """创建标准的 twins/{slug}/knowledge/ 目录结构。"""
    knowledge_root = base_dir / slug / "knowledge"
    knowledge_root.mkdir(parents=True, exist_ok=True)
    return knowledge_root


# ─────────────────────────────────────────────────────────────────────────────
# 测试：干净的 twin（无需修复）
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditCleanTwin:
    """测试 audit_twin() 对干净数据的处理。"""

    def test_clean_twin_returns_empty_findings(self, tmp_path: Path):
        """干净 twin 的所有 chunks 经 _llm_scrub 后无抽象，findings 应为空列表。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        context_dir = knowledge_root / "coworker"
        _make_knowledge_file(
            context_dir,
            "data.json",
            [
                {"id": 0, "text": "他在项目管理方面很有经验，经常用甘特图", "metadata": {}},
                {"id": 1, "text": "She's great at negotiating deals", "metadata": {}},
            ],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("unchanged", {})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["total_findings"] == 0
        assert report["findings"] == []

    def test_clean_twin_report_has_zero_total(self, tmp_path: Path):
        """report.json 应有 'total_findings': 0 字段。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "coworker",
            "data.json",
            [{"id": 0, "text": "clean text", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("clean text", {})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["total_findings"] == 0
        assert "findings" in report


# ─────────────────────────────────────────────────────────────────────────────
# 测试：有个人叙述的 twin（需要修复）
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditDirtyTwin:
    """测试 audit_twin() 对含个人叙述数据的处理。"""

    def test_chunk_rewritten_in_place(self, tmp_path: Path):
        """被标记的 chunk 应在原 JSON 文件中被覆写为脱敏版本。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        data_file = _make_knowledge_file(
            knowledge_root / "partner",
            "messages.json",
            [{"id": 0, "text": "昨天和老婆吵了一架，因为花钱的事情", "metadata": {}}],
        )

        scrubbed_text = "[RELATIONSHIP_CONFLICT: 家庭财务争吵]"
        abstractions = {"[RELATIONSHIP_CONFLICT]": 1}

        with patch("tools.privacy_auditor._llm_scrub", return_value=(scrubbed_text, abstractions)):
            audit_twin("test-twin", tmp_path)

        # 读取修改后的文件验证内容已被替换
        doc = json.loads(data_file.read_text(encoding="utf-8"))
        assert doc["chunks"][0]["text"] == scrubbed_text

    def test_finding_recorded_in_report(self, tmp_path: Path):
        """被修复的 chunk 应在报告的 findings 列表中有记录。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "partner",
            "messages.json",
            [{"id": 5, "text": "personal content", "metadata": {}}],
        )

        abstractions = {"[PERSONAL_NARRATIVE]": 1}
        with patch("tools.privacy_auditor._llm_scrub", return_value=("abstracted", abstractions)):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["total_findings"] == 1
        assert len(report["findings"]) == 1
        finding = report["findings"][0]
        assert finding["chunk_id"] == 5
        assert finding["abstractions"] == abstractions

    def test_report_does_not_contain_before_field(self, tmp_path: Path):
        """隐私要求：报告 findings 中不得包含 'before' 字段（原始文本）。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "partner",
            "messages.json",
            [{"id": 0, "text": "my personal story", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("abstracted", {"[PERSONAL_NARRATIVE]": 1})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        for finding in report["findings"]:
            assert "before" not in finding, "报告不应包含 'before' 原始文本字段"

    def test_report_does_not_contain_after_field(self, tmp_path: Path):
        """隐私要求：报告 findings 中不得包含 'after' 字段（修复后文本）。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "partner",
            "messages.json",
            [{"id": 0, "text": "my personal story", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("abstracted", {"[PERSONAL_NARRATIVE]": 1})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        for finding in report["findings"]:
            assert "after" not in finding, "报告不应包含 'after' 修复后文本字段"

    def test_finding_has_required_keys_only(self, tmp_path: Path):
        """finding 对象应只包含 file、chunk_id、abstractions 字段。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "partner",
            "messages.json",
            [{"id": 3, "text": "something personal", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("scrubbed", {"[PERSONAL_NARRATIVE]": 1})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        finding = report["findings"][0]
        assert "file" in finding
        assert "chunk_id" in finding
        assert "abstractions" in finding

    def test_multiple_chunks_multiple_findings(self, tmp_path: Path):
        """多个被标记的 chunk 应分别记录为独立的 findings。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "family",
            "messages.json",
            [
                {"id": 0, "text": "personal 1", "metadata": {}},
                {"id": 1, "text": "behavioral signal — keep", "metadata": {}},
                {"id": 2, "text": "personal 2", "metadata": {}},
            ],
        )

        def mock_scrub(text):
            if "behavioral" in text:
                return (text, {})
            return ("abstracted", {"[PERSONAL_NARRATIVE]": 1})

        with patch("tools.privacy_auditor._llm_scrub", side_effect=mock_scrub):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["total_findings"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 测试：报告文件位置
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditReportLocation:
    """测试审计报告写入正确位置。"""

    def test_report_written_to_correct_path(self, tmp_path: Path):
        """报告应写入 {base_dir}/{slug}/privacy_audit_report.json。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "coworker",
            "data.json",
            [{"id": 0, "text": "clean text", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("clean text", {})):
            report_path = audit_twin("test-twin", tmp_path)

        expected_path = tmp_path / "test-twin" / "privacy_audit_report.json"
        assert report_path == expected_path
        assert expected_path.exists()

    def test_report_is_valid_json(self, tmp_path: Path):
        """报告文件应是合法的 JSON。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "coworker",
            "data.json",
            [{"id": 0, "text": "text", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("text", {})):
            report_path = audit_twin("test-twin", tmp_path)

        # Should not raise
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert isinstance(report, dict)

    def test_report_has_required_top_level_fields(self, tmp_path: Path):
        """报告应包含 slug、audited_at、total_findings、total_files_modified、findings 字段。"""
        from tools.privacy_auditor import audit_twin

        knowledge_root = _make_twin_structure(tmp_path)
        _make_knowledge_file(
            knowledge_root / "coworker",
            "data.json",
            [{"id": 0, "text": "text", "metadata": {}}],
        )

        with patch("tools.privacy_auditor._llm_scrub", return_value=("text", {})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert "slug" in report
        assert "audited_at" in report
        assert "total_findings" in report
        assert "total_files_modified" in report
        assert "findings" in report


# ─────────────────────────────────────────────────────────────────────────────
# 测试：空 knowledge 目录
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditEmptyKnowledge:
    """测试 audit_twin() 对空 knowledge 目录的处理。"""

    def test_empty_knowledge_dir_no_crash(self, tmp_path: Path):
        """空 knowledge 目录不应引发异常。"""
        from tools.privacy_auditor import audit_twin

        _make_twin_structure(tmp_path)  # knowledge/ dir exists but empty

        with patch("tools.privacy_auditor._llm_scrub", return_value=("text", {})):
            report_path = audit_twin("test-twin", tmp_path)

        assert report_path.exists()

    def test_empty_knowledge_dir_zero_findings(self, tmp_path: Path):
        """空 knowledge 目录的报告应有零 findings。"""
        from tools.privacy_auditor import audit_twin

        _make_twin_structure(tmp_path)

        with patch("tools.privacy_auditor._llm_scrub", return_value=("text", {})):
            report_path = audit_twin("test-twin", tmp_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["total_findings"] == 0
        assert report["findings"] == []


# ─────────────────────────────────────────────────────────────────────────────
# 测试：CLI 接口
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditCLI:
    """测试 privacy_auditor.py CLI 命令行接口。"""

    def test_help_flag_exits_zero(self):
        """--help 标志应输出使用说明并以退出码 0 退出。"""
        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "tools/privacy_auditor.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env={**__import__("os").environ, "PYTHONPATH": str(project_root)},
        )
        assert result.returncode == 0
        assert "--slug" in result.stdout

    def test_cli_runs_on_clean_twin(self, tmp_path: Path):
        """CLI 对干净 twin 应以退出码 0 完成。"""
        project_root = Path(__file__).resolve().parent.parent

        # Create minimal twin structure
        knowledge_root = _make_twin_structure(tmp_path, "audit-test")
        _make_knowledge_file(
            knowledge_root / "coworker",
            "data.json",
            [{"id": 0, "text": "clean behavioral text", "metadata": {}}],
            twin_slug="audit-test",
        )

        import os
        env = {**os.environ, "PYTHONPATH": str(project_root)}
        # No API key — _llm_scrub will gracefully degrade
        env.pop("ANTHROPIC_API_KEY", None)

        result = subprocess.run(
            [
                sys.executable,
                "tools/privacy_auditor.py",
                "--slug", "audit-test",
                "--base-dir", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=env,
        )
        assert result.returncode == 0
