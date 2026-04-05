from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


class TestVersionManagerBackup:
    def test_backup_creates_version_dir(self, tmp_path):
        """PLAT-03: Backup creates a version archive."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        twin_dir.mkdir(parents=True)
        meta = {"name": "Test", "slug": "test-twin", "version": "v1"}
        (twin_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        assert (twin_dir / "versions" / "v1" / "meta.json").exists()

    def test_backup_includes_knowledge(self, tmp_path):
        twin_dir = tmp_path / "twins" / "test-twin"
        knowledge_dir = twin_dir / "knowledge" / "coworker"
        knowledge_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (knowledge_dir / "test.json").write_text('{"test": true}', encoding="utf-8")

        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        assert (twin_dir / "versions" / "v1" / "knowledge" / "coworker" / "test.json").exists()


class TestVersionManagerRollback:
    def test_rollback_restores_meta(self, tmp_path):
        """PLAT-03: Rollback restores previous twin state."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        twin_dir.mkdir(parents=True)

        # Create v1 state
        meta_v1 = {"name": "Test", "slug": "test-twin", "version": "v1"}
        (twin_dir / "meta.json").write_text(json.dumps(meta_v1), encoding="utf-8")

        # Backup v1
        subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )

        # Modify to v2
        meta_v2 = {"name": "Test Updated", "slug": "test-twin", "version": "v2"}
        (twin_dir / "meta.json").write_text(json.dumps(meta_v2), encoding="utf-8")

        # Rollback to v1
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "rollback", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0

        # Verify meta.json is back to v1
        restored_meta = json.loads((twin_dir / "meta.json").read_text(encoding="utf-8"))
        assert restored_meta["version"] == "v1"
        assert restored_meta["name"] == "Test"


class TestVersionManagerList:
    def test_list_versions(self, tmp_path):
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        (twin_dir / "versions" / "v1").mkdir(parents=True)
        (twin_dir / "versions" / "v2").mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{}', encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "list", "--slug", "test-twin",
             "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        assert "v1" in result.stdout
        assert "v2" in result.stdout


class TestVersionManagerImports:
    def test_no_colleague_skill_reference(self):
        with open("tools/version_manager.py", encoding="utf-8") as f:
            content = f.read()
        assert "colleague-skill" not in content
        assert "colleague_skill" not in content
        assert ".openclaw" not in content

    def test_uses_twin_files(self):
        with open("tools/version_manager.py", encoding="utf-8") as f:
            content = f.read()
        assert "TWIN_FILES" in content
