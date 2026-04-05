from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestStorageIntegrity:
    """PRIV-04: Knowledge directory contains only scrubbed JSON, no raw text."""

    def test_wechat_produces_json_only(self, sample_chat_csv, tmp_path):
        subprocess.run(
            [sys.executable, "tools/wechat_parser.py",
             "--file", str(sample_chat_csv),
             "--context", "partner", "--slug", "integrity-test",
             "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        knowledge_dir = tmp_path / "twins" / "integrity-test" / "knowledge" / "partner"
        all_files = list(knowledge_dir.rglob("*"))
        non_json = [f for f in all_files if f.is_file() and f.suffix != ".json"]
        assert non_json == [], f"Non-JSON files found in knowledge/: {non_json}"

    def test_json_has_scrub_stats(self, sample_chat_csv, tmp_path):
        subprocess.run(
            [sys.executable, "tools/wechat_parser.py",
             "--file", str(sample_chat_csv),
             "--context", "coworker", "--slug", "integrity-test",
             "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        knowledge_dir = tmp_path / "twins" / "integrity-test" / "knowledge" / "coworker"
        for json_file in knowledge_dir.glob("*.json"):
            doc = json.loads(json_file.read_text(encoding="utf-8"))
            assert "scrub_stats" in doc, f"Missing scrub_stats in {json_file}"
            assert "schema_version" in doc
            assert "context_label" in doc

    def test_text_ingestor_produces_json_only(self, tmp_path):
        subprocess.run(
            [sys.executable, "tools/text_ingestor.py",
             "--text", "测试内容 13800138000",
             "--context", "friend", "--slug", "integrity-test",
             "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        knowledge_dir = tmp_path / "twins" / "integrity-test" / "knowledge" / "friend"
        all_files = list(knowledge_dir.rglob("*"))
        non_json = [f for f in all_files if f.is_file() and f.suffix != ".json"]
        assert non_json == [], f"Non-JSON files found: {non_json}"

    def test_no_raw_pii_in_stored_json(self, sample_chat_csv, tmp_path):
        """Verify that stored JSON content does not contain raw PII from fixture."""
        subprocess.run(
            [sys.executable, "tools/wechat_parser.py",
             "--file", str(sample_chat_csv),
             "--context", "partner", "--slug", "pii-check",
             "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        knowledge_dir = tmp_path / "twins" / "pii-check" / "knowledge" / "partner"
        for json_file in knowledge_dir.glob("*.json"):
            content = json_file.read_text(encoding="utf-8")
            # Fixture CSV contains these raw PII values
            assert "13812345678" not in content, "Raw phone number found in stored JSON"
            assert "test@example.com" not in content, "Raw email found in stored JSON"


class TestNoColleagueSkillReferences:
    """Verify complete migration from colleague-skill namespace."""

    def test_no_colleague_skill_in_tools(self):
        tools_dir = Path("tools")
        for py_file in tools_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "colleague-skill" not in content, f"{py_file} still references colleague-skill"
            assert ".colleague-skill" not in content, f"{py_file} still references .colleague-skill config"
