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


class TestTextIngestorCLI:
    def test_context_flag_required(self):
        result = _run(
            [sys.executable, "tools/text_ingestor.py", "--text", "hello", "--slug", "test"],
        )
        assert result.returncode != 0

    def test_help_shows_options(self):
        result = _run(
            [sys.executable, "tools/text_ingestor.py", "--help"],
        )
        assert "--context" in result.stdout
        assert "--text" in result.stdout
        assert "--file" in result.stdout


class TestMarkdownIngestion:
    """INGEST-05: Markdown file import."""

    def test_markdown_file(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "# 标题\n\n这是内容。联系电话13800138000。\n\n## 第二节\n\n更多内容。",
            encoding="utf-8",
        )
        result = _run(
            [
                sys.executable, "tools/text_ingestor.py",
                "--file", str(md_file),
                "--context", "coworker",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode == 0, f"Ingestor failed: {result.stderr}"

        json_files = list(
            (tmp_path / "twins" / "test-twin" / "knowledge" / "coworker").glob("markdown_*.json")
        )
        assert len(json_files) == 1
        doc = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert doc["source_type"] == "markdown"
        assert doc["chunk_count"] >= 1
        # PII should be scrubbed
        all_text = " ".join(c["text"] for c in doc["chunks"])
        assert "13800138000" not in all_text
        assert "[PHONE]" in all_text


class TestPlaintextIngestion:
    """INGEST-06: Plain text paste input."""

    def test_inline_text(self, tmp_path):
        result = _run(
            [
                sys.executable, "tools/text_ingestor.py",
                "--text", "你好，我的邮箱是test@example.com，请联系。",
                "--context", "friend",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode == 0, f"Ingestor failed: {result.stderr}"

        json_files = list(
            (tmp_path / "twins" / "test-twin" / "knowledge" / "friend").glob("plaintext_*.json")
        )
        assert len(json_files) == 1
        doc = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert doc["source_type"] == "plaintext"
        assert doc["chunk_count"] >= 1
        all_text = " ".join(c["text"] for c in doc["chunks"])
        assert "test@example.com" not in all_text
        assert "[EMAIL]" in all_text

    def test_stdin_input(self, tmp_path):
        result = _run(
            [
                sys.executable, "tools/text_ingestor.py",
                "--context", "family",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
            input="从标准输入读取的内容。手机号13912345678。",
        )
        assert result.returncode == 0
        json_files = list(
            (tmp_path / "twins" / "test-twin" / "knowledge" / "family").glob("plaintext_*.json")
        )
        assert len(json_files) == 1


class TestTextIngestorImports:
    def test_imports_pii_scrubber(self):
        path = Path(PROJECT_ROOT) / "tools" / "text_ingestor.py"
        content = path.read_text(encoding="utf-8")
        assert "from tools.pii_scrubber import scrub" in content

    def test_imports_ingestion_output(self):
        path = Path(PROJECT_ROOT) / "tools" / "text_ingestor.py"
        content = path.read_text(encoding="utf-8")
        assert "write_ingestion_json" in content
