from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Project root so subprocess calls can import tools.*
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a script with PYTHONPATH set to project root."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(args, capture_output=True, text=True, cwd=PROJECT_ROOT, env=env, **kwargs)


class TestFeishuCollectorCLI:
    """Test that feishu_auto_collector.py has the right CLI interface."""

    def test_context_flag_required(self):
        """INGEST-01 + INGEST-07: --context is required."""
        result = _run(
            [sys.executable, "tools/feishu_auto_collector.py", "--name", "test", "--slug", "test"],
        )
        # Should fail because --context is missing
        assert result.returncode != 0
        assert "context" in result.stderr.lower() or "required" in result.stderr.lower()

    def test_slug_flag_required(self):
        result = _run(
            [sys.executable, "tools/feishu_auto_collector.py", "--name", "test", "--context", "coworker"],
        )
        assert result.returncode != 0

    def test_help_shows_context(self):
        result = _run(
            [sys.executable, "tools/feishu_auto_collector.py", "--help"],
        )
        assert "--context" in result.stdout
        assert "--slug" in result.stdout


class TestFeishuCollectorImports:
    """Verify correct imports are present."""

    def test_imports_pii_scrubber(self):
        path = Path(PROJECT_ROOT) / "tools" / "feishu_auto_collector.py"
        content = path.read_text(encoding="utf-8")
        assert "from tools.pii_scrubber import scrub" in content

    def test_imports_ingestion_output(self):
        path = Path(PROJECT_ROOT) / "tools" / "feishu_auto_collector.py"
        content = path.read_text(encoding="utf-8")
        assert "ingestion_output" in content

    def test_no_colleague_skill_reference(self):
        path = Path(PROJECT_ROOT) / "tools" / "feishu_auto_collector.py"
        content = path.read_text(encoding="utf-8")
        assert "colleague-skill" not in content
        assert "colleague_skill" not in content
