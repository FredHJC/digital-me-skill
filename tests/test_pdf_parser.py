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


try:
    import pymupdf4llm
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


class TestPDFParserCLI:
    def test_context_flag_required(self):
        result = _run(
            [sys.executable, "tools/pdf_parser.py", "--file", "test.pdf", "--slug", "test"],
        )
        assert result.returncode != 0

    def test_help_shows_context(self):
        result = _run(
            [sys.executable, "tools/pdf_parser.py", "--help"],
        )
        assert "--context" in result.stdout


@pytest.mark.skipif(not HAS_PYMUPDF, reason="pymupdf4llm not installed")
class TestPDFParserParsing:
    def test_parse_sample_pdf(self, tmp_path):
        """Parse fixture PDF and verify JSON output."""
        fixture_pdf = Path(PROJECT_ROOT) / "tests" / "fixtures" / "sample.pdf"
        if not fixture_pdf.exists():
            pytest.skip("sample.pdf fixture not available")

        result = _run(
            [
                sys.executable, "tools/pdf_parser.py",
                "--file", str(fixture_pdf),
                "--context", "coworker",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode == 0, f"Parser failed: {result.stderr}"

        json_files = list((tmp_path / "twins" / "test-twin" / "knowledge" / "coworker").glob("pdf_*.json"))
        assert len(json_files) >= 1
        doc = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert doc["schema_version"] == "1.0"
        assert doc["source_type"] == "pdf"
        assert doc["chunk_count"] >= 1

    def test_nonexistent_pdf_fails(self, tmp_path):
        result = _run(
            [
                sys.executable, "tools/pdf_parser.py",
                "--file", str(tmp_path / "nonexistent.pdf"),
                "--context", "coworker",
                "--slug", "test",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        assert result.returncode != 0


class TestPDFParserImports:
    def test_imports_pii_scrubber(self):
        path = Path(PROJECT_ROOT) / "tools" / "pdf_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "from tools.pii_scrubber import scrub" in content

    def test_imports_pymupdf4llm(self):
        path = Path(PROJECT_ROOT) / "tools" / "pdf_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "pymupdf4llm" in content
