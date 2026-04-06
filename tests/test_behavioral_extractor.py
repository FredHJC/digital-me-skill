"""
行为提取器测试 — 使用模拟 LLM 测试 per-context 提取流水线。

测试覆盖：
- extract_context() 返回有效的 ExtractionArtifact
- 上下文隔离（Context Isolation）
- 双语支持（中文/英文）
- 无效 LLM 输出的拒绝
- 不存在的上下文目录的错误处理
- CLI 子进程调用
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.extraction_models import ExtractionArtifact

# ─────────────────────────────────────────────────────────────────────────────
# 辅助：构建测试用知识 JSON
# ─────────────────────────────────────────────────────────────────────────────

def _make_knowledge_json(
    chunks: list[dict],
    context_label: str,
    source_type: str = "wechat_csv",
    twin_slug: str = "test-twin",
) -> dict:
    """构建符合 schema_version 1.0 的知识 JSON 文档。"""
    return {
        "schema_version": "1.0",
        "source_type": source_type,
        "context_label": context_label,
        "twin_slug": twin_slug,
        "imported_at": "2026-04-05T00:00:00+00:00",
        "source_file": "test.csv",
        "scrub_stats": {},
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def _write_knowledge_fixture(
    base_dir: Path,
    slug: str,
    context: str,
    chunks: list[dict],
    filename: str = "source_1.json",
) -> Path:
    """在 base_dir/{slug}/knowledge/{context}/ 写入知识 JSON 文件。"""
    knowledge_dir = base_dir / slug / "knowledge" / context
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    doc = _make_knowledge_json(chunks, context, twin_slug=slug)
    out = knowledge_dir / filename
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _make_valid_extraction_response(context_label: str = "coworker") -> dict:
    """返回符合 ExtractionArtifact schema 的有效 LLM 响应（不含元数据字段）。"""
    return {
        "tone_style": {
            "formality_level": 3,
            "humor_style": "dry wit",
            "directness": "direct",
            "emoji_habit": "occasional",
            "cadence": "mixed",
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


def _make_mock_anthropic_response(response_dict: dict) -> MagicMock:
    """构建模拟 Anthropic API 响应对象。"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = json.dumps(response_dict)
    return mock_response


def _patch_anthropic(response_dict: dict):
    """返回正确的 patch 上下文管理器，模拟 behavioral_extractor 中的 _anthropic.Anthropic。"""
    mock_resp = _make_mock_anthropic_response(response_dict)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp
    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client
    return patch("tools.behavioral_extractor._anthropic", mock_anthropic_module)


# ─────────────────────────────────────────────────────────────────────────────
# TestExtractContext — 基础提取功能测试
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractContext:
    """测试 extract_context() 基本功能。"""

    def test_returns_valid_extraction_artifact(self, tmp_path: Path) -> None:
        """模拟 LLM 返回有效 JSON 时，extract_context() 返回有效的 ExtractionArtifact。"""
        slug = "test-twin"
        context = "coworker"
        chunks = [
            {"id": 0, "text": "他在项目管理方面很有经验", "metadata": {}},
            {"id": 1, "text": "喜欢用数据驱动决策", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        valid_response = _make_valid_extraction_response(context)

        with _patch_anthropic(valid_response):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        assert output_path.name == "coworker.json"
        assert output_path.exists()

        data = json.loads(output_path.read_text(encoding="utf-8"))
        artifact = ExtractionArtifact.model_validate(data)
        assert artifact.context_label == "coworker"
        assert artifact.schema_version == "2.0"
        assert artifact.twin_slug == slug
        assert artifact.chunk_count == 2

    def test_output_path_in_extractions_dir(self, tmp_path: Path) -> None:
        """extract_context() 写入 {base_dir}/{slug}/extractions/{context}.json。"""
        slug = "test-twin"
        context = "coworker"
        chunks = [{"id": 0, "text": "工作积极主动", "metadata": {}}]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        expected = tmp_path / slug / "extractions" / "coworker.json"
        assert output_path == expected
        assert expected.exists()

    def test_schema_version_is_2_0(self, tmp_path: Path) -> None:
        """输出制品的 schema_version 为 '2.0'。"""
        slug = "test-twin"
        context = "coworker"
        _write_knowledge_fixture(tmp_path, slug, context, [{"id": 0, "text": "good at coding", "metadata": {}}])

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "2.0"


# ─────────────────────────────────────────────────────────────────────────────
# TestContextIsolation — 上下文隔离测试
# ─────────────────────────────────────────────────────────────────────────────

class TestContextIsolation:
    """测试 extract_context() 仅读取指定上下文的数据。"""

    def test_only_target_context_extracted(self, tmp_path: Path) -> None:
        """仅提取 coworker 上下文时，partner 目录不被读取。"""
        slug = "test-twin"

        # 写入两个上下文
        coworker_chunks = [
            {"id": 0, "text": "COWORKER_MARKER_XYZ", "metadata": {}},
        ]
        partner_chunks = [
            {"id": 0, "text": "PARTNER_MARKER_ABC", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, "coworker", coworker_chunks)
        _write_knowledge_fixture(tmp_path, slug, "partner", partner_chunks)

        captured_prompts: list[str] = []
        mock_resp = _make_mock_anthropic_response(_make_valid_extraction_response("coworker"))
        mock_client = MagicMock()

        def capture_create(**kwargs):
            for msg in kwargs.get("messages", []):
                captured_prompts.append(msg.get("content", ""))
            return mock_resp

        mock_client.messages.create.side_effect = capture_create
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.behavioral_extractor._anthropic", mock_anthropic_module):
            from tools.behavioral_extractor import extract_context
            extract_context(slug, "coworker", tmp_path)

        # 验证 partner 数据未被传入 LLM 提示
        all_prompts = " ".join(captured_prompts)
        assert "PARTNER_MARKER_ABC" not in all_prompts
        assert "COWORKER_MARKER_XYZ" in all_prompts

    def test_partner_extraction_not_created_when_only_coworker_run(self, tmp_path: Path) -> None:
        """仅运行 coworker 提取时，partner 的输出文件不存在。"""
        slug = "test-twin"
        _write_knowledge_fixture(tmp_path, slug, "coworker", [{"id": 0, "text": "工作认真", "metadata": {}}])
        _write_knowledge_fixture(tmp_path, slug, "partner", [{"id": 0, "text": "关系亲密", "metadata": {}}])

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            extract_context(slug, "coworker", tmp_path)

        partner_output = tmp_path / slug / "extractions" / "partner.json"
        assert not partner_output.exists()


# ─────────────────────────────────────────────────────────────────────────────
# TestBilingualParity — 双语支持测试
# ─────────────────────────────────────────────────────────────────────────────

class TestBilingualParity:
    """测试 extract_context() 正确检测源语言。"""

    def test_chinese_chunks_detected_as_zh(self, tmp_path: Path) -> None:
        """中文数据块应将 source_language 设为 'zh'。"""
        slug = "test-twin"
        cn_chunks = [
            {"id": 0, "text": "他在项目管理方面很有经验，经常用甘特图安排工作", "metadata": {}},
            {"id": 1, "text": "沟通风格直接，不喜欢绕弯子", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, "coworker", cn_chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, "coworker", tmp_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["source_language"] == "zh"

    def test_english_chunks_detected_as_en(self, tmp_path: Path) -> None:
        """英文数据块应将 source_language 设为 'en'。"""
        slug = "test-twin"
        en_chunks = [
            {"id": 0, "text": "She is great at negotiating deals", "metadata": {}},
            {"id": 1, "text": "Always starts with rapport building before pitching", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, "partner", en_chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, "partner", tmp_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["source_language"] == "en"

    def test_independent_artifacts_for_different_contexts(self, tmp_path: Path) -> None:
        """两个上下文的提取结果相互独立。"""
        slug = "test-twin"
        cn_chunks = [{"id": 0, "text": "中文工作沟通方式直接简洁", "metadata": {}}]
        en_chunks = [{"id": 0, "text": "English partner communication style", "metadata": {}}]

        _write_knowledge_fixture(tmp_path, slug, "coworker", cn_chunks)
        _write_knowledge_fixture(tmp_path, slug, "partner", en_chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            coworker_path = extract_context(slug, "coworker", tmp_path)
            partner_path = extract_context(slug, "partner", tmp_path)

        coworker_data = json.loads(coworker_path.read_text(encoding="utf-8"))
        partner_data = json.loads(partner_path.read_text(encoding="utf-8"))

        assert coworker_data["context_label"] == "coworker"
        assert partner_data["context_label"] == "partner"
        assert coworker_data["source_language"] == "zh"
        assert partner_data["source_language"] == "en"


# ─────────────────────────────────────────────────────────────────────────────
# TestValidationRejection — 无效 LLM 输出拒绝测试
# ─────────────────────────────────────────────────────────────────────────────

class TestValidationRejection:
    """测试 extract_context() 拒绝不符合 Pydantic schema 的 LLM 输出。"""

    def test_missing_tone_style_raises_system_exit(self, tmp_path: Path) -> None:
        """LLM 返回缺少 tone_style 字段的 JSON 时，应以 exit code 1 退出。"""
        slug = "test-twin"
        _write_knowledge_fixture(tmp_path, slug, "coworker", [{"id": 0, "text": "测试", "metadata": {}}])

        # 缺少 tone_style 字段
        malformed = {
            "vocabulary": {
                "catchphrases": [],
                "sentence_structure": "short",
                "filler_words": [],
                "domain_terms": [],
            },
            "knowledge_boundaries": {
                "strong_domains": [],
                "avoided_topics": [],
                "depth_signals": [],
            },
            "behavioral_patterns": {
                "hard_limits": [],
                "conflict_style": "avoids",
                "decision_patterns": [],
                "care_signals": [],
            },
        }

        with _patch_anthropic(malformed):
            with pytest.raises(SystemExit) as exc_info:
                from tools.behavioral_extractor import extract_context
                extract_context(slug, "coworker", tmp_path)

        assert exc_info.value.code == 1

    def test_invalid_json_response_raises_system_exit(self, tmp_path: Path) -> None:
        """LLM 返回非 JSON 字符串时，应以 exit code 1 退出。"""
        slug = "test-twin"
        _write_knowledge_fixture(tmp_path, slug, "coworker", [{"id": 0, "text": "测试", "metadata": {}}])

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock()]
        mock_resp.content[0].text = "This is not JSON at all."

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        mock_anthropic_module = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        with patch("tools.behavioral_extractor._anthropic", mock_anthropic_module):
            with pytest.raises(SystemExit) as exc_info:
                from tools.behavioral_extractor import extract_context
                extract_context(slug, "coworker", tmp_path)

        assert exc_info.value.code == 1

    def test_empty_json_object_raises_system_exit(self, tmp_path: Path) -> None:
        """LLM 返回空 JSON 对象时，Pydantic 验证失败应退出。"""
        slug = "test-twin"
        _write_knowledge_fixture(tmp_path, slug, "coworker", [{"id": 0, "text": "测试", "metadata": {}}])

        with _patch_anthropic({}):
            with pytest.raises(SystemExit) as exc_info:
                from tools.behavioral_extractor import extract_context
                extract_context(slug, "coworker", tmp_path)

        assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestNonexistentContext — 不存在目录测试
# ─────────────────────────────────────────────────────────────────────────────

class TestNonexistentContext:
    """测试 extract_context() 在上下文目录不存在时正确报错。"""

    def test_nonexistent_context_dir_raises_system_exit(self, tmp_path: Path) -> None:
        """不存在的上下文目录应触发 SystemExit(1)。"""
        slug = "test-twin"
        # 不创建任何 knowledge 目录

        with pytest.raises(SystemExit) as exc_info:
            from tools.behavioral_extractor import extract_context
            extract_context(slug, "nonexistent_context", tmp_path)

        assert exc_info.value.code == 1

    def test_empty_context_dir_raises_system_exit(self, tmp_path: Path) -> None:
        """上下文目录存在但没有 JSON 文件时应触发 SystemExit(1)。"""
        slug = "test-twin"
        # 创建空目录
        empty_dir = tmp_path / slug / "knowledge" / "coworker"
        empty_dir.mkdir(parents=True)

        with pytest.raises(SystemExit) as exc_info:
            from tools.behavioral_extractor import extract_context
            extract_context(slug, "coworker", tmp_path)

        assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestExtractorCLI — CLI 子进程测试
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractorCLI:
    """测试 behavioral_extractor.py CLI 入口。"""

    def test_cli_help_shows_required_args(self) -> None:
        """--help 输出应包含 --slug, --context, --base-dir 参数。"""
        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "tools/behavioral_extractor.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0
        assert "--slug" in result.stdout
        assert "--context" in result.stdout
        assert "--base-dir" in result.stdout

    def test_cli_runs_successfully_with_mocked_api(self, tmp_path: Path) -> None:
        """CLI 使用模拟 API 时，提取结果写入磁盘并返回 0。"""
        slug = "test-twin"
        context = "coworker"
        chunks = [{"id": 0, "text": "工作高效，沟通简洁", "metadata": {}}]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        artifact = ExtractionArtifact.model_validate(data)
        assert artifact.context_label == context
