from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Project root so subprocess calls can import tools.*
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a script with PYTHONPATH set to project root."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(args, capture_output=True, text=True, cwd=PROJECT_ROOT, env=env, **kwargs)


class TestWeChatParserCLI:
    def test_context_flag_required(self):
        result = _run(
            [sys.executable, "tools/wechat_parser.py", "--file", "test.csv", "--slug", "test"],
        )
        assert result.returncode != 0

    def test_help_shows_context(self):
        result = _run(
            [sys.executable, "tools/wechat_parser.py", "--help"],
        )
        assert "--context" in result.stdout
        assert "--file" in result.stdout


class TestWeChatParserParsing:
    def test_parse_fixture_csv(self, sample_chat_csv, tmp_path):
        """Parse the sample CSV fixture and verify JSON output."""
        result = _run(
            [
                sys.executable, "tools/wechat_parser.py",
                "--file", str(sample_chat_csv),
                "--context", "partner",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode == 0, f"Parser failed: {result.stderr}"

        # Verify JSON output was created
        knowledge_dir = tmp_path / "twins" / "test-twin" / "knowledge" / "partner"
        json_files = list(knowledge_dir.glob("wechat_csv_*.json"))
        assert len(json_files) == 1, f"Expected 1 JSON file, found {len(json_files)} in {knowledge_dir}"

        # Verify JSON content
        doc = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert doc["schema_version"] == "1.0"
        assert doc["source_type"] == "wechat_csv"
        assert doc["context_label"] == "partner"

        # conftest sample_chat_csv fixture: rows with IsSender=1 AND Type=1:
        # Row 0: IsSender=1, Type=1 (contains phone 13912345678) -> included
        # Row 1: IsSender=1, Type=1 (contains email test@example.com) -> included
        # Row 2: IsSender=0, Type=3 -> excluded (not sender, not text)
        # Row 3: IsSender=0, Type=1 -> excluded (not sender)
        # Row 4: IsSender=1, Type=1 (明天见) -> included
        assert doc["chunk_count"] == 3
        assert len(doc["chunks"]) == 3

        # Verify PII was scrubbed (fixture contains phone number 13912345678)
        first_chunk_text = doc["chunks"][0]["text"]
        assert "13912345678" not in first_chunk_text
        assert "[PHONE]" in first_chunk_text

    def test_rejects_bad_schema(self, tmp_path):
        """WeChat parser should fail on CSV with wrong columns."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("Name,Message,Time\nBob,Hello,12345\n", encoding="utf-8")
        result = _run(
            [
                sys.executable, "tools/wechat_parser.py",
                "--file", str(bad_csv),
                "--context", "coworker",
                "--slug", "test",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode != 0
        assert "缺少必要列" in result.stderr or "required" in result.stderr.lower()

    def test_scrub_stats_present(self, sample_chat_csv, tmp_path):
        result = _run(
            [
                sys.executable, "tools/wechat_parser.py",
                "--file", str(sample_chat_csv),
                "--context", "friend",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode == 0
        json_files = list((tmp_path / "twins" / "test-twin" / "knowledge" / "friend").glob("*.json"))
        doc = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert "scrub_stats" in doc
        # conftest fixture CSV contains phone and email PII in sent messages
        assert doc["scrub_stats"].get("[PHONE]", 0) >= 1


class TestWeChatParserImports:
    def test_imports_pii_scrubber(self):
        path = Path(PROJECT_ROOT) / "tools" / "wechat_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "from tools.pii_scrubber import scrub" in content

    def test_imports_ingestion_output(self):
        path = Path(PROJECT_ROOT) / "tools" / "wechat_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "write_ingestion_json" in content
