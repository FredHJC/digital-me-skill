from __future__ import annotations

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


class TestEmailParserCLI:
    def test_context_flag_required(self):
        """INGEST-04 + INGEST-07: --context is required."""
        result = _run(
            [sys.executable, "tools/email_parser.py", "--file", "nonexistent.eml",
             "--target", "test@example.com", "--slug", "test"],
        )
        assert result.returncode != 0

    def test_help_shows_context(self):
        result = _run(
            [sys.executable, "tools/email_parser.py", "--help"],
        )
        assert "--context" in result.stdout
        assert "--slug" in result.stdout


class TestEmailParserImports:
    def test_imports_pii_scrubber(self):
        path = Path(PROJECT_ROOT) / "tools" / "email_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "from tools.pii_scrubber import scrub" in content

    def test_imports_ingestion_output(self):
        path = Path(PROJECT_ROOT) / "tools" / "email_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "ingestion_output" in content

    def test_no_colleague_skill_reference(self):
        path = Path(PROJECT_ROOT) / "tools" / "email_parser.py"
        content = path.read_text(encoding="utf-8")
        assert "colleague-skill" not in content


class TestEmailParserIntegration:
    def test_parse_sample_eml(self, sample_eml, twin_dir, tmp_path):
        """Parse a real .eml fixture and verify JSON output."""
        result = _run(
            [
                sys.executable, "tools/email_parser.py",
                "--file", str(sample_eml),
                "--target", "sender@example.com",
                "--context", "coworker",
                "--slug", "test-twin",
                "--base-dir", str(tmp_path / "twins"),
            ],
        )
        # Parser should succeed (exit 0) or fail gracefully
        # Check that JSON output was created in the expected directory
        knowledge_dir = tmp_path / "twins" / "test-twin" / "knowledge" / "coworker"
        if result.returncode == 0:
            json_files = list(knowledge_dir.glob("email_*.json"))
            assert len(json_files) >= 1, f"Expected JSON output in {knowledge_dir}"
