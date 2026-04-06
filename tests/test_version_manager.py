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


class TestVersionManagerPhase3:
    """Phase 3: Tests for core.md in TWIN_FILES and facets/ backup/rollback (D-09)."""

    def test_twin_files_includes_core_md(self):
        """TWIN_FILES constant must contain 'core.md' for Phase 3."""
        with open("tools/version_manager.py", encoding="utf-8") as f:
            content = f.read()
        # Find the TWIN_FILES line and verify core.md appears on it
        for line in content.splitlines():
            if "TWIN_FILES" in line and "=" in line:
                assert '"core.md"' in line or "'core.md'" in line, (
                    f"core.md not found in TWIN_FILES line: {line!r}"
                )
                return
        pytest.fail("TWIN_FILES constant not found in version_manager.py")

    def test_backup_copies_core_md(self, tmp_path):
        """Backup with core.md present must copy core.md to versions/{version}/core.md."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        twin_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (twin_dir / "core.md").write_text("# Core Identity\n\nPhase 3 core content.", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        backed_up_core = twin_dir / "versions" / "v1" / "core.md"
        assert backed_up_core.exists(), "core.md was not copied to the version archive"
        assert backed_up_core.read_text(encoding="utf-8") == "# Core Identity\n\nPhase 3 core content."

    def test_backup_copies_facets_dir(self, tmp_path):
        """Backup with facets/ directory must copy entire facets/ tree to versions/{version}/facets/."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        facets_dir = twin_dir / "facets"
        facets_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (facets_dir / "coworker.md").write_text("# Coworker Facet\n\nAdaptations here.", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        backed_up_facet = twin_dir / "versions" / "v1" / "facets" / "coworker.md"
        assert backed_up_facet.exists(), "facets/coworker.md was not copied to the version archive"
        assert backed_up_facet.read_text(encoding="utf-8") == "# Coworker Facet\n\nAdaptations here."

    def test_rollback_restores_core_md(self, tmp_path):
        """Rollback must restore core.md from version archive to twin root."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        twin_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (twin_dir / "core.md").write_text("v1 content", encoding="utf-8")

        # Backup v1
        subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )

        # Overwrite core.md with v2 content
        (twin_dir / "core.md").write_text("v2 content", encoding="utf-8")

        # Rollback to v1
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "rollback", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        restored = (twin_dir / "core.md").read_text(encoding="utf-8")
        assert restored == "v1 content", f"Expected 'v1 content', got {restored!r}"

    def test_rollback_restores_facets_dir(self, tmp_path):
        """Rollback must restore facets/ directory from version archive, replacing current facets/."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        facets_dir = twin_dir / "facets"
        facets_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (facets_dir / "coworker.md").write_text("v1 facet", encoding="utf-8")

        # Backup v1
        subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )

        # Overwrite facet with v2 content
        (facets_dir / "coworker.md").write_text("v2 facet", encoding="utf-8")

        # Rollback to v1
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "rollback", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        restored = (facets_dir / "coworker.md").read_text(encoding="utf-8")
        assert restored == "v1 facet", f"Expected 'v1 facet', got {restored!r}"

    def test_rollback_creates_facets_when_missing(self, tmp_path):
        """Rollback must create facets/ from archive when it doesn't exist in twin root."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-twin"
        facets_dir = twin_dir / "facets"
        facets_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (facets_dir / "coworker.md").write_text("original facet content", encoding="utf-8")

        # Backup v1 (with facets/)
        subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )

        # Delete facets/ entirely
        shutil.rmtree(facets_dir)
        assert not facets_dir.exists(), "facets/ should have been deleted"

        # Rollback to v1
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "rollback", "--slug", "test-twin",
             "--version", "v1", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0
        assert facets_dir.exists(), "facets/ was not recreated after rollback"
        restored = (facets_dir / "coworker.md").read_text(encoding="utf-8")
        assert restored == "original facet content"


class TestSkillMdBackupRollback:
    """Phase 4: Tests for SKILL*.md backup and rollback (T-04-07, T-04-08)."""

    def test_backup_captures_skill_files(self, tmp_path):
        """backup() must copy all SKILL*.md files into the versioned archive."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-slug"
        twin_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (twin_dir / "SKILL.md").write_text("# SKILL default\n", encoding="utf-8")
        (twin_dir / "SKILL-coworker.md").write_text("# SKILL coworker\n", encoding="utf-8")
        (twin_dir / "SKILL-partner.md").write_text("# SKILL partner\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-slug",
             "--version", "v-skill-test", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0

        version_dir = twin_dir / "versions" / "v-skill-test"
        assert (version_dir / "SKILL.md").exists(), "SKILL.md was not copied to archive"
        assert (version_dir / "SKILL-coworker.md").exists(), "SKILL-coworker.md was not copied to archive"
        assert (version_dir / "SKILL-partner.md").exists(), "SKILL-partner.md was not copied to archive"

        assert (version_dir / "SKILL.md").read_text(encoding="utf-8") == "# SKILL default\n"
        assert (version_dir / "SKILL-coworker.md").read_text(encoding="utf-8") == "# SKILL coworker\n"
        assert (version_dir / "SKILL-partner.md").read_text(encoding="utf-8") == "# SKILL partner\n"

    def test_rollback_restores_skill_files(self, tmp_path):
        """rollback() must restore SKILL*.md files from the version archive."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-slug"
        twin_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (twin_dir / "SKILL.md").write_text("original SKILL content\n", encoding="utf-8")
        (twin_dir / "SKILL-coworker.md").write_text("original coworker content\n", encoding="utf-8")

        # Backup v-restore-test
        subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-slug",
             "--version", "v-restore-test", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )

        # Overwrite SKILL.md and delete SKILL-coworker.md (simulating a newer generation)
        (twin_dir / "SKILL.md").write_text("overwritten SKILL content\n", encoding="utf-8")
        (twin_dir / "SKILL-coworker.md").unlink()

        # Rollback to v-restore-test
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "rollback", "--slug", "test-slug",
             "--version", "v-restore-test", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0

        restored_skill = (twin_dir / "SKILL.md").read_text(encoding="utf-8")
        assert restored_skill == "original SKILL content\n", (
            f"SKILL.md not restored correctly: {restored_skill!r}"
        )
        assert (twin_dir / "SKILL-coworker.md").exists(), "SKILL-coworker.md was not restored"
        restored_coworker = (twin_dir / "SKILL-coworker.md").read_text(encoding="utf-8")
        assert restored_coworker == "original coworker content\n"

    def test_rollback_removes_stale_skill_files(self, tmp_path):
        """rollback() must remove SKILL*.md files that did not exist in the backed-up version."""
        import subprocess, sys
        twin_dir = tmp_path / "twins" / "test-slug"
        twin_dir.mkdir(parents=True)
        (twin_dir / "meta.json").write_text('{"version": "v1"}', encoding="utf-8")
        (twin_dir / "SKILL.md").write_text("base SKILL\n", encoding="utf-8")
        (twin_dir / "SKILL-coworker.md").write_text("coworker SKILL\n", encoding="utf-8")

        # Backup v-stale-test (only SKILL.md + SKILL-coworker.md at this point)
        subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "backup", "--slug", "test-slug",
             "--version", "v-stale-test", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )

        # Add a new SKILL-partner.md (simulating a new facet added after backup)
        (twin_dir / "SKILL-partner.md").write_text("partner SKILL added after backup\n", encoding="utf-8")

        # Rollback to v-stale-test
        result = subprocess.run(
            [sys.executable, "tools/version_manager.py",
             "--action", "rollback", "--slug", "test-slug",
             "--version", "v-stale-test", "--base-dir", str(tmp_path / "twins")],
            capture_output=True, text=True, cwd=".",
        )
        assert result.returncode == 0

        assert not (twin_dir / "SKILL-partner.md").exists(), (
            "SKILL-partner.md should have been removed as a stale file during rollback"
        )
        assert (twin_dir / "SKILL.md").exists(), "SKILL.md should be restored"
        assert (twin_dir / "SKILL-coworker.md").exists(), "SKILL-coworker.md should be restored"
