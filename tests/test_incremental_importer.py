"""
增量导入器测试 — 测试单上下文增量更新流水线的隔离性、备份和隐私守卫。

测试覆盖（INGEST-08）：
- 预检：core.md 缺失、twin 目录缺失、空 context 标签
- 版本管理：backup 在 extract_context 之前调用
- 增量写入：新 JSON 文件写入正确的 knowledge 目录
- 隔离性：兄弟提取制品和 facet 不被修改，core.md 不被修改
- 隐私守卫：generate_skill_files 被调用（内含 validate_no_raw_text）
- meta.json：updated_at 变更，last_incremental_context 记录目标上下文
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.incremental_importer import incremental_import


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _make_valid_extraction_dict(context_label: str = "coworker") -> dict:
    """返回符合 ExtractionArtifact schema 的完整提取制品（含元数据字段）。"""
    return {
        "schema_version": "2.0",
        "twin_slug": "test-twin",
        "context_label": context_label,
        "source_language": "zh",
        "extracted_at": "2026-04-05T00:00:00+00:00",
        "chunk_count": 5,
        "tone_style": {
            "formality_level": 3,
            "humor_style": "dry wit",
            "directness": "direct",
            "emoji_habit": "occasional",
            "cadence": "measured",
        },
        "vocabulary": {
            "catchphrases": ["好的", "没问题"],
            "sentence_structure": "short and punchy",
            "filler_words": ["嗯", "那个"],
            "domain_terms": ["OKR", "迭代"],
        },
        "knowledge_boundaries": {
            "strong_domains": ["product management", "agile"],
            "avoided_topics": ["personal finances"],
            "depth_signals": ["frequently cites first principles"],
        },
        "behavioral_patterns": {
            "hard_limits": ["never shares salary publicly"],
            "conflict_style": "avoids direct confrontation",
            "decision_patterns": ["uses data to justify decisions"],
            "care_signals": ["deflects personal questions with humor"],
        },
    }


def _make_extraction_fixture(
    base_dir: Path,
    slug: str,
    context: str,
    chunk_count: int = 5,
) -> Path:
    """在 base_dir/{slug}/extractions/{context}.json 创建提取制品文件，同时确保 meta.json 存在。"""
    extraction_data = _make_valid_extraction_dict(context)
    extraction_data["twin_slug"] = slug
    extraction_data["chunk_count"] = chunk_count

    twin_dir = base_dir / slug
    twin_dir.mkdir(parents=True, exist_ok=True)

    # 确保 meta.json 存在
    meta_path = twin_dir / "meta.json"
    if not meta_path.exists():
        meta = {
            "name": slug,
            "slug": slug,
            "context_labels": [context],
            "version": "v1",
            "created_at": "2026-04-05T00:00:00+00:00",
            "updated_at": "2026-04-05T00:00:00+00:00",
            "knowledge_sources": [],
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 写入提取制品
    extractions_dir = twin_dir / "extractions"
    extractions_dir.mkdir(parents=True, exist_ok=True)
    output_path = extractions_dir / f"{context}.json"
    output_path.write_text(
        json.dumps(extraction_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _make_valid_facet_response(context: str = "coworker") -> str:
    """返回有效的 facet Markdown 响应（以继承标记开头）。"""
    return f"""# test-twin — {context} Facet

> Inherits from core.md — only context-specific adaptations below.

## Behavioral Rules

在工作环境中正式程度略高，更注重清晰的表达。

## Tone & Style

使用专业术语，简洁明了。

## Vocabulary

常用工作场景术语，如迭代、复盘、对齐。

## Knowledge Boundaries

（与 core 一致）

## Behavioral Limits

在工作边界上更加明确，不轻易妥协核心原则。
"""


def _make_valid_core_response() -> str:
    """返回有效的 core.md Markdown 响应（仅行为描述，不含长引号）。"""
    return """# test-twin — Core Identity

> 数据来源上下文：coworker, partner

## Identity

偏好逻辑驱动的沟通方式，在不同场合保持一致的工作态度。

## Behavioral Rules

行为规则占位符。

## Tone & Style

正式程度适中，偶尔使用幽默缓解紧张气氛。

## Vocabulary

常用词汇包括专业术语，句式简洁。

## Knowledge Boundaries

擅长产品管理和敏捷开发领域。

## Behavioral Limits

决策依赖数据支撑，冲突时倾向于回避对抗。
"""


def _file_digest(path: Path) -> str:
    """计算文件内容的 SHA-256 摘要。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_input_json(tmp_path: Path, filename: str = "input_batch.json") -> Path:
    """创建一个符合规范的预脱敏 JSON 输入文件。"""
    input_data = {
        "schema_version": "1.0",
        "source_type": "wechat_csv",
        "context_label": "partner",
        "twin_slug": "test-twin",
        "imported_at": "2026-04-05T00:00:00+00:00",
        "source_file": "chat.csv",
        "scrub_stats": {},
        "chunk_count": 2,
        "chunks": [
            {"id": 0, "text": "关心家人，周末一起出行", "metadata": {}},
            {"id": 1, "text": "对新鲜事物好奇，愿意尝试", "metadata": {}},
        ],
    }
    input_file = tmp_path / filename
    input_file.write_text(json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return input_file


def _setup_complete_twin(
    base_dir: Path,
    slug: str,
    contexts: list[str],
) -> Path:
    """创建完整的 twin 目录，包含 core.md、meta.json、extractions、facets 和 knowledge。"""
    twin_dir = base_dir / slug
    twin_dir.mkdir(parents=True, exist_ok=True)

    # 创建 meta.json
    meta = {
        "name": slug,
        "slug": slug,
        "context_labels": contexts,
        "version": "v1",
        "created_at": "2026-04-05T00:00:00+00:00",
        "updated_at": "2026-04-05T00:00:00+00:00",
        "knowledge_sources": [],
    }
    (twin_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 创建 core.md
    (twin_dir / "core.md").write_text(_make_valid_core_response(), encoding="utf-8")

    # 为每个上下文创建 extractions、facets 和 knowledge
    for ctx in contexts:
        # extractions/{ctx}.json
        extraction_data = _make_valid_extraction_dict(ctx)
        extraction_data["twin_slug"] = slug
        extractions_dir = twin_dir / "extractions"
        extractions_dir.mkdir(parents=True, exist_ok=True)
        (extractions_dir / f"{ctx}.json").write_text(
            json.dumps(extraction_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # facets/{ctx}.md
        facets_dir = twin_dir / "facets"
        facets_dir.mkdir(parents=True, exist_ok=True)
        (facets_dir / f"{ctx}.md").write_text(
            _make_valid_facet_response(ctx), encoding="utf-8"
        )

        # knowledge/{ctx}/ 目录及一个占位符 JSON
        knowledge_dir = twin_dir / "knowledge" / ctx
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        dummy_ingestion = {
            "schema_version": "1.0",
            "source_type": "manual",
            "context_label": ctx,
            "twin_slug": slug,
            "imported_at": "2026-04-05T00:00:00+00:00",
            "source_file": "manual.txt",
            "scrub_stats": {},
            "chunk_count": 1,
            "chunks": [{"id": 0, "text": f"{ctx} 示例数据", "metadata": {}}],
        }
        (knowledge_dir / "manual_20260405T000000.json").write_text(
            json.dumps(dummy_ingestion, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return twin_dir


def _patch_extractor_anthropic(response_dict: dict):
    """返回正确的 patch 上下文管理器，模拟 behavioral_extractor 中的 _anthropic.Anthropic。"""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=json.dumps(response_dict))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp
    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client
    return patch("tools.behavioral_extractor._anthropic", mock_anthropic_module)


def _patch_synthesizer_anthropic(response_text: str):
    """返回正确的 patch 上下文管理器，模拟 twin_synthesizer 中的 _anthropic.Anthropic。"""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp
    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client
    return patch("tools.twin_synthesizer._anthropic", mock_anthropic_module)


# ─────────────────────────────────────────────────────────────────────────────
# TestPreFlight — 预检测试
# ─────────────────────────────────────────────────────────────────────────────

class TestPreFlight:
    """测试增量导入器的预检逻辑（参数验证和目录状态验证）。"""

    def test_missing_core_md_exits_1(self, tmp_path: Path, capsys) -> None:
        """twin_dir 存在但无 core.md 时，incremental_import 应以 exit 1 退出并打印 'core.md' 到 stderr。"""
        slug = "test-twin"
        twin_dir = tmp_path / slug
        twin_dir.mkdir(parents=True)
        # 不创建 core.md

        input_json = _make_input_json(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            incremental_import(slug, "partner", input_json, tmp_path)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "core.md" in captured.err

    def test_missing_twin_dir_exits_1(self, tmp_path: Path) -> None:
        """twin 目录不存在时，incremental_import 应以 exit 1 退出。"""
        slug = "nonexistent-twin"
        input_json = _make_input_json(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            incremental_import(slug, "partner", input_json, tmp_path)

        assert exc_info.value.code == 1

    def test_empty_context_label_exits_1(self, tmp_path: Path) -> None:
        """空 context 字符串应导致 exit 1。"""
        slug = "test-twin"
        twin_dir = tmp_path / slug
        twin_dir.mkdir(parents=True)
        (twin_dir / "core.md").write_text("# Core\n", encoding="utf-8")
        input_json = _make_input_json(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            incremental_import(slug, "", input_json, tmp_path)

        assert exc_info.value.code == 1

    def test_missing_meta_json_exits_1(self, tmp_path: Path, capsys) -> None:
        """twin_dir 有 core.md 但无 meta.json 时，应以 exit 1 退出并打印 'meta.json' 到 stderr。"""
        slug = "test-twin"
        twin_dir = tmp_path / slug
        twin_dir.mkdir(parents=True)
        # 创建 core.md 但不创建 meta.json
        (twin_dir / "core.md").write_text("# Core\n", encoding="utf-8")
        input_json = _make_input_json(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            incremental_import(slug, "partner", input_json, tmp_path)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "meta.json" in captured.err


# ─────────────────────────────────────────────────────────────────────────────
# TestVersioning — 版本备份顺序测试
# ─────────────────────────────────────────────────────────────────────────────

class TestVersioning:
    """测试 backup 在 extract_context 之前被调用。"""

    def test_backup_created_before_update(self, tmp_path: Path) -> None:
        """version_manager.backup 必须在 extract_context 之前被调用（call_args_list 顺序验证）。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        call_order: list[str] = []

        def mock_backup(twin_dir, version_name):
            call_order.append("backup")
            return True

        def mock_extract_context(slug, context, base_dir):
            call_order.append("extract_context")
            return tmp_path / slug / "extractions" / f"{context}.json"

        def mock_synthesize_facet(slug, context, base_dir, hints=None):
            return tmp_path / slug / "facets" / f"{context}.md"

        def mock_generate_skill_files(slug, name, base_dir):
            return []

        with patch("tools.version_manager.backup", side_effect=mock_backup), \
             patch("tools.behavioral_extractor.extract_context", side_effect=mock_extract_context), \
             patch("tools.twin_synthesizer.synthesize_facet", side_effect=mock_synthesize_facet), \
             patch("tools.twin_skill_writer.generate_skill_files", side_effect=mock_generate_skill_files):
            incremental_import(slug, "partner", input_json, tmp_path)

        # backup が extract_context より先に呼ばれること
        assert "backup" in call_order
        assert "extract_context" in call_order
        backup_idx = call_order.index("backup")
        extract_idx = call_order.index("extract_context")
        assert backup_idx < extract_idx, (
            f"backup (idx={backup_idx}) must be called before extract_context (idx={extract_idx})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TestIncrementalIngest — 增量写入路径测试
# ─────────────────────────────────────────────────────────────────────────────

class TestIncrementalIngest:
    """测试增量导入将输入文件正确写入 knowledge 目录。"""

    def test_writes_to_correct_context_dir(self, tmp_path: Path) -> None:
        """导入后，knowledge/{context}/ 目录中有新的 JSON 文件。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        knowledge_dir_before = tmp_path / slug / "knowledge" / "partner"
        files_before = set(knowledge_dir_before.glob("*.json")) if knowledge_dir_before.exists() else set()

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]):
            incremental_import(slug, "partner", input_json, tmp_path)

        files_after = set((tmp_path / slug / "knowledge" / "partner").glob("*.json"))
        new_files = files_after - files_before
        assert len(new_files) >= 1, "Should have at least one new JSON file in knowledge/partner/"


# ─────────────────────────────────────────────────────────────────────────────
# TestIncrementalIsolation — 兄弟文件隔离测试
# ─────────────────────────────────────────────────────────────────────────────

class TestIncrementalIsolation:
    """测试增量导入不修改兄弟提取制品、facet 文件和 core.md。"""

    def test_sibling_extraction_unchanged(self, tmp_path: Path) -> None:
        """导入到 'partner' 后，extractions/coworker.json 的 SHA-256 摘要不变。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        sibling_path = tmp_path / slug / "extractions" / "coworker.json"
        digest_before = _file_digest(sibling_path)

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]):
            incremental_import(slug, "partner", input_json, tmp_path)

        digest_after = _file_digest(sibling_path)
        assert digest_before == digest_after, (
            "extractions/coworker.json should be byte-for-byte identical after importing to 'partner'"
        )

    def test_sibling_facets_unchanged(self, tmp_path: Path) -> None:
        """导入到 'partner' 后，facets/coworker.md 的 SHA-256 摘要不变。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        sibling_facet = tmp_path / slug / "facets" / "coworker.md"
        digest_before = _file_digest(sibling_facet)

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]):
            incremental_import(slug, "partner", input_json, tmp_path)

        digest_after = _file_digest(sibling_facet)
        assert digest_before == digest_after, (
            "facets/coworker.md should be byte-for-byte identical after importing to 'partner'"
        )

    def test_core_md_unchanged(self, tmp_path: Path) -> None:
        """导入到 'partner' 后，core.md 的 SHA-256 摘要不变。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        core_path = tmp_path / slug / "core.md"
        digest_before = _file_digest(core_path)

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]):
            incremental_import(slug, "partner", input_json, tmp_path)

        digest_after = _file_digest(core_path)
        assert digest_before == digest_after, (
            "core.md should be byte-for-byte identical after incremental import"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TestPrivacyRegression — 隐私守卫回归测试
# ─────────────────────────────────────────────────────────────────────────────

class TestPrivacyRegression:
    """测试增量导入完成后隐私守卫（通过 generate_skill_files）被触发。"""

    def test_privacy_gate_runs_after_update(self, tmp_path: Path) -> None:
        """generate_skill_files 应被调用（其内部运行 validate_no_raw_text 守卫）。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]) as mock_gen:
            incremental_import(slug, "partner", input_json, tmp_path)

        mock_gen.assert_called_once()

    def test_updated_skill_has_injection_shield(self, tmp_path: Path) -> None:
        """增量导入后，生成的 SKILL 文件包含 '## Behavioral Rules' 节。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner"])
        input_json = _make_input_json(tmp_path)

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")):
            # Use real generate_skill_files to verify output content
            with patch("tools.twin_skill_writer._load_shield", return_value="## Behavioral Rules\n\nShield content.\n"):
                incremental_import(slug, "partner", input_json, tmp_path)

        # Verify at least one SKILL*.md file was produced and contains the shield section
        skill_files = list((tmp_path / slug).glob("SKILL*.md"))
        assert len(skill_files) >= 1, "At least one SKILL file should be generated"
        combined_content = "".join(f.read_text(encoding="utf-8") for f in skill_files)
        assert "## Behavioral Rules" in combined_content, (
            "Generated SKILL files should contain '## Behavioral Rules' injection shield section"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TestMetaUpdate — meta.json 更新测试
# ─────────────────────────────────────────────────────────────────────────────

class TestMetaUpdate:
    """测试增量导入后 meta.json 的 updated_at 和 last_incremental_context 字段更新。"""

    def test_meta_updated_at_changes(self, tmp_path: Path) -> None:
        """成功导入后，meta.json 的 updated_at 时间戳应变更。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        meta_path = tmp_path / slug / "meta.json"
        meta_before = json.loads(meta_path.read_text(encoding="utf-8"))
        updated_at_before = meta_before["updated_at"]

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]):
            incremental_import(slug, "partner", input_json, tmp_path)

        meta_after = json.loads(meta_path.read_text(encoding="utf-8"))
        updated_at_after = meta_after["updated_at"]
        assert updated_at_after != updated_at_before, (
            "meta.json updated_at should change after a successful incremental import"
        )

    def test_meta_last_incremental_context(self, tmp_path: Path) -> None:
        """成功导入后，meta.json 应含 last_incremental_context 字段，值为目标 context 标签。"""
        slug = "test-twin"
        _setup_complete_twin(tmp_path, slug, ["partner", "coworker"])
        input_json = _make_input_json(tmp_path)

        with _patch_extractor_anthropic(_make_valid_extraction_dict("partner")), \
             _patch_synthesizer_anthropic(_make_valid_facet_response("partner")), \
             patch("tools.twin_skill_writer.generate_skill_files", return_value=[]):
            incremental_import(slug, "partner", input_json, tmp_path)

        meta_path = tmp_path / slug / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "last_incremental_context" in meta, (
            "meta.json should contain 'last_incremental_context' after incremental import"
        )
        assert meta["last_incremental_context"] == "partner", (
            f"last_incremental_context should be 'partner', got {meta.get('last_incremental_context')!r}"
        )
