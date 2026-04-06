"""
双子合成器测试 — 使用模拟 LLM 测试 two-pass 合成流水线。

测试覆盖：
- synthesize_core() 从多上下文提取制品生成 core.md
- synthesize_facet() 从单上下文 + core.md 生成 facets/{context}.md
- --hints 注入用户指导
- validate_no_raw_text() 隐私守卫
- meta.json 更新
- 自动备份
- CLI 入口
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.extraction_models import ExtractionArtifact


# ─────────────────────────────────────────────────────────────────────────────
# 辅助：构建测试用提取制品 JSON 并写入磁盘
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


def _make_valid_core_response() -> str:
    """返回有效的 core.md Markdown 响应（仅行为描述，不含长引号）。"""
    return """# test-twin — Core Identity

> 数据来源上下文：coworker, partner

## Identity

偏好逻辑驱动的沟通方式，在不同场合保持一致的工作态度。对问题有系统性思考习惯。

## Tone & Style

正式程度适中，偶尔使用幽默缓解紧张气氛。表达直接，节奏稳定。

## Vocabulary

常用词汇包括专业术语，句式简洁。

## Knowledge Boundaries

擅长产品管理和敏捷开发领域，对个人财务话题保持低调。

## Behavioral Limits

决策依赖数据支撑，冲突时倾向于回避对抗。
"""


def _make_valid_facet_response(context: str = "coworker") -> str:
    """返回有效的 facet Markdown 响应（以继承标记开头）。"""
    return f"""# test-twin — {context} Facet

> Inherits from core.md — only context-specific adaptations below.

## Tone & Style

在工作环境中正式程度略高，更注重清晰的表达。

## Vocabulary

常用工作场景术语，如迭代、复盘、对齐。

## Knowledge Boundaries

（与 core 一致）

## Behavioral Limits

在工作边界上更加明确，不轻易妥协核心原则。
"""


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
# TestSynthesizeCore — 核心合成测试
# ─────────────────────────────────────────────────────────────────────────────

class TestSynthesizeCore:
    """测试 synthesize_core() 基本功能。"""

    def test_produces_core_md(self, tmp_path: Path) -> None:
        """2 个提取制品 -> core.md 存在且包含预期内容。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")
        _make_extraction_fixture(tmp_path, slug, "partner")

        with _patch_synthesizer_anthropic(_make_valid_core_response()):
            from tools.twin_synthesizer import synthesize_core
            output_path = synthesize_core(slug, tmp_path)

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert len(content) > 50

    def test_single_context_warning(self, tmp_path: Path, capsys) -> None:
        """1 个提取制品 -> core.md 生成成功，stderr 含 '警告'。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        with _patch_synthesizer_anthropic(_make_valid_core_response()):
            from tools.twin_synthesizer import synthesize_core
            output_path = synthesize_core(slug, tmp_path)

        assert output_path.exists()
        captured = capsys.readouterr()
        assert "警告" in captured.err

    def test_core_sections_present(self, tmp_path: Path) -> None:
        """生成的 core.md 包含所有预期节（## Identity 等）。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")
        _make_extraction_fixture(tmp_path, slug, "partner")

        with _patch_synthesizer_anthropic(_make_valid_core_response()):
            from tools.twin_synthesizer import synthesize_core
            output_path = synthesize_core(slug, tmp_path)

        content = output_path.read_text(encoding="utf-8")
        assert "## Identity" in content
        assert "## Tone & Style" in content
        assert "## Vocabulary" in content
        assert "## Knowledge Boundaries" in content
        assert "## Behavioral Limits" in content


# ─────────────────────────────────────────────────────────────────────────────
# TestSynthesizeFacet — 上下文专属合成测试
# ─────────────────────────────────────────────────────────────────────────────

class TestSynthesizeFacet:
    """测试 synthesize_facet() 基本功能。"""

    def test_produces_facet_md(self, tmp_path: Path) -> None:
        """core.md 存在 + 提取制品 -> facets/{context}.md 存在。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        # 先创建 core.md
        twin_dir = tmp_path / slug
        core_path = twin_dir / "core.md"
        core_path.write_text(_make_valid_core_response(), encoding="utf-8")

        with _patch_synthesizer_anthropic(_make_valid_facet_response("coworker")):
            from tools.twin_synthesizer import synthesize_facet
            output_path = synthesize_facet(slug, "coworker", tmp_path)

        assert output_path.exists()

    def test_facet_inheritance_marker(self, tmp_path: Path) -> None:
        """facets/{context}.md 以 'Inherits from core.md' 开头（D-08）。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        twin_dir = tmp_path / slug
        core_path = twin_dir / "core.md"
        core_path.write_text(_make_valid_core_response(), encoding="utf-8")

        with _patch_synthesizer_anthropic(_make_valid_facet_response("coworker")):
            from tools.twin_synthesizer import synthesize_facet
            output_path = synthesize_facet(slug, "coworker", tmp_path)

        content = output_path.read_text(encoding="utf-8")
        assert "Inherits from core.md" in content

    def test_facet_file_naming(self, tmp_path: Path) -> None:
        """context='coworker' -> facets/coworker.md（ROLE-02）。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        twin_dir = tmp_path / slug
        core_path = twin_dir / "core.md"
        core_path.write_text(_make_valid_core_response(), encoding="utf-8")

        with _patch_synthesizer_anthropic(_make_valid_facet_response("coworker")):
            from tools.twin_synthesizer import synthesize_facet
            output_path = synthesize_facet(slug, "coworker", tmp_path)

        expected_path = tmp_path / slug / "facets" / "coworker.md"
        assert output_path == expected_path
        assert expected_path.exists()


# ─────────────────────────────────────────────────────────────────────────────
# TestHintsInjection — 用户补充说明注入测试
# ─────────────────────────────────────────────────────────────────────────────

class TestHintsInjection:
    """测试 --hints 标志对提示词的影响。"""

    def test_hints_in_prompt(self, tmp_path: Path) -> None:
        """--hints 'speaks formally' -> LLM 收到的提示词中包含 'speaks formally'。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        captured_prompts: list[str] = []

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=_make_valid_core_response())]
        mock_client = MagicMock()

        def capture_create(**kwargs):
            for msg in kwargs.get("messages", []):
                captured_prompts.append(msg.get("content", ""))
            return mock_resp

        mock_client.messages.create.side_effect = capture_create
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.twin_synthesizer._anthropic", mock_anthropic_module):
            from tools.twin_synthesizer import synthesize_core
            synthesize_core(slug, tmp_path, hints="speaks formally")

        all_prompts = " ".join(captured_prompts)
        assert "speaks formally" in all_prompts

    def test_no_hints_default(self, tmp_path: Path) -> None:
        """无 --hints -> LLM 收到的提示词中包含 '（无用户补充说明）'。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        captured_prompts: list[str] = []

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=_make_valid_core_response())]
        mock_client = MagicMock()

        def capture_create(**kwargs):
            for msg in kwargs.get("messages", []):
                captured_prompts.append(msg.get("content", ""))
            return mock_resp

        mock_client.messages.create.side_effect = capture_create
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.twin_synthesizer._anthropic", mock_anthropic_module):
            from tools.twin_synthesizer import synthesize_core
            synthesize_core(slug, tmp_path, hints=None)

        all_prompts = " ".join(captured_prompts)
        assert "（无用户补充说明）" in all_prompts


# ─────────────────────────────────────────────────────────────────────────────
# TestPrivacyScrubGate — 隐私守卫测试
# ─────────────────────────────────────────────────────────────────────────────

class TestPrivacyScrubGate:
    """测试 validate_no_raw_text() 对合成输出的拦截。"""

    def test_core_violation_blocks_write(self, tmp_path: Path) -> None:
        """LLM 返回含超过 80 字符引号字符串 -> exit 1，core.md 不被写入。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        # 含超过 80 字符的引号字符串（触发 validate_no_raw_text）
        bad_response = '## Identity\n\n"' + 'x' * 85 + '"\n\n## Tone & Style\n\n正常描述。\n'

        with _patch_synthesizer_anthropic(bad_response):
            from tools.twin_synthesizer import synthesize_core
            with pytest.raises(SystemExit) as exc_info:
                synthesize_core(slug, tmp_path)

        assert exc_info.value.code == 1
        # core.md 不应被写入
        core_path = tmp_path / slug / "core.md"
        assert not core_path.exists()

    def test_facet_violation_blocks_write(self, tmp_path: Path) -> None:
        """LLM 返回含假电子邮件的 facet 输出 -> exit 1，facet 文件不被写入。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        twin_dir = tmp_path / slug
        core_path = twin_dir / "core.md"
        core_path.write_text(_make_valid_core_response(), encoding="utf-8")

        # 含电子邮件地址（触发 validate_no_raw_text）
        bad_response = "# Facet\n\n> Inherits from core.md — only context-specific adaptations below.\n\n## Tone & Style\n\n联系方式：fake@example.com\n"

        with _patch_synthesizer_anthropic(bad_response):
            from tools.twin_synthesizer import synthesize_facet
            with pytest.raises(SystemExit) as exc_info:
                synthesize_facet(slug, "coworker", tmp_path)

        assert exc_info.value.code == 1
        # facet 文件不应被写入
        facet_path = tmp_path / slug / "facets" / "coworker.md"
        assert not facet_path.exists()


# ─────────────────────────────────────────────────────────────────────────────
# TestMetaUpdate — meta.json 更新测试
# ─────────────────────────────────────────────────────────────────────────────

class TestMetaUpdate:
    """测试 synthesize_all() 后 meta.json 的更新。"""

    def test_meta_updated_after_synthesis(self, tmp_path: Path) -> None:
        """synthesize_all() 完成后，meta.json 含 synthesized_at 和 synthesized_contexts。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")
        _make_extraction_fixture(tmp_path, slug, "partner")

        # 先更新 meta.json 中的 context_labels
        twin_dir = tmp_path / slug
        meta_path = twin_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["context_labels"] = ["coworker", "partner"]
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        call_count = [0]

        def make_response(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                # 第一次调用：core 合成
                resp = MagicMock()
                resp.content = [MagicMock(text=_make_valid_core_response())]
                return resp
            else:
                # 后续调用：facet 合成
                context = "coworker" if idx == 1 else "partner"
                resp = MagicMock()
                resp.content = [MagicMock(text=_make_valid_facet_response(context))]
                return resp

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = make_response
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.twin_synthesizer._anthropic", mock_anthropic_module):
            from tools.twin_synthesizer import synthesize_all
            synthesize_all(slug, tmp_path)

        meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "synthesized_at" in meta_data
        assert "synthesized_contexts" in meta_data
        assert isinstance(meta_data["synthesized_contexts"], list)
        assert len(meta_data["synthesized_contexts"]) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# TestAutoBackup — 自动备份测试
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoBackup:
    """测试 synthesize_all() 在覆盖时自动备份。"""

    def test_auto_backup_before_overwrite(self, tmp_path: Path) -> None:
        """core.md 已存在时 synthesize_all() -> versions/ 含 pre-synth 备份。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")

        twin_dir = tmp_path / slug

        # 预先创建 core.md（模拟之前的合成结果）
        core_path = twin_dir / "core.md"
        core_path.write_text("# Old core content\n", encoding="utf-8")

        call_count = [0]

        def make_response(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            resp = MagicMock()
            if idx == 0:
                resp.content = [MagicMock(text=_make_valid_core_response())]
            else:
                resp.content = [MagicMock(text=_make_valid_facet_response("coworker"))]
            return resp

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = make_response
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.twin_synthesizer._anthropic", mock_anthropic_module):
            from tools.twin_synthesizer import synthesize_all
            synthesize_all(slug, tmp_path)

        versions_dir = twin_dir / "versions"
        assert versions_dir.exists()
        version_dirs = list(versions_dir.iterdir())
        assert len(version_dirs) >= 1
        # 确认备份目录以 pre-synth 开头
        assert any("pre-synth" in d.name for d in version_dirs)


# ─────────────────────────────────────────────────────────────────────────────
# TestSynthesizerCLI — CLI 入口测试
# ─────────────────────────────────────────────────────────────────────────────

class TestSynthesizerCLI:
    """测试 twin_synthesizer.py CLI 入口。"""

    def test_help_output(self) -> None:
        """--help 应包含 --slug, --hints, --base-dir, --mode 参数。"""
        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "tools/twin_synthesizer.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0
        assert "--slug" in result.stdout
        assert "--hints" in result.stdout
        assert "--base-dir" in result.stdout
        assert "--mode" in result.stdout

    def test_end_to_end_mocked(self, tmp_path: Path) -> None:
        """使用 monkeypatched _anthropic 的端对端测试 — 验证 core.md + facets/ 被创建。"""
        slug = "test-twin"
        _make_extraction_fixture(tmp_path, slug, "coworker")
        _make_extraction_fixture(tmp_path, slug, "partner")

        # 更新 meta.json 的 context_labels
        twin_dir = tmp_path / slug
        meta_path = twin_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["context_labels"] = ["coworker", "partner"]
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        call_count = [0]

        def make_response(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            resp = MagicMock()
            if idx == 0:
                resp.content = [MagicMock(text=_make_valid_core_response())]
            elif idx == 1:
                resp.content = [MagicMock(text=_make_valid_facet_response("coworker"))]
            else:
                resp.content = [MagicMock(text=_make_valid_facet_response("partner"))]
            return resp

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = make_response
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.twin_synthesizer._anthropic", mock_anthropic_module):
            from tools.twin_synthesizer import synthesize_all
            synthesize_all(slug, tmp_path)

        # 验证 core.md 和 facets/ 目录存在
        assert (twin_dir / "core.md").exists()
        assert (twin_dir / "facets").exists()
        facet_files = list((twin_dir / "facets").glob("*.md"))
        assert len(facet_files) == 2
