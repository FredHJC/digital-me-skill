"""
后提取验证器测试 — 测试 validate_no_raw_text() 函数和端到端集成流水线。

测试覆盖：
- validate_no_raw_text() 对干净的行为描述文本通过
- validate_no_raw_text() 检测长引号字符串违规
- validate_no_raw_text() 检测未脱敏手机号
- validate_no_raw_text() 检测未脱敏电子邮箱
- validate_no_raw_text() 对抽象标签文本通过
- validate_no_raw_text() 对现有占位符通过
- 端到端集成：extract_context() 从 knowledge/ 到 extractions/ 完整验证
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.extraction_models import ExtractionArtifact, validate_no_raw_text


# ─────────────────────────────────────────────────────────────────────────────
# 辅助：构建测试夹具
# ─────────────────────────────────────────────────────────────────────────────

def _make_valid_extraction_response() -> dict:
    """返回有效的四维提取 JSON（不含元数据字段）。"""
    return {
        "tone_style": {
            "formality_level": 3,
            "humor_style": "dry wit",
            "directness": "direct",
            "emoji_habit": "occasional",
            "cadence": "mixed",
        },
        "vocabulary": {
            "catchphrases": ["好的", "明白了"],
            "sentence_structure": "short and direct",
            "filler_words": ["嗯", "那个"],
            "domain_terms": ["OKR", "迭代", "产品路线图"],
        },
        "knowledge_boundaries": {
            "strong_domains": ["product management", "agile methodology"],
            "avoided_topics": ["personal finances", "family matters"],
            "depth_signals": ["frequently cites first principles"],
        },
        "behavioral_limits": {
            "hard_nos": ["never shares salary publicly"],
            "conflict_style": "avoids direct confrontation",
            "decision_patterns": ["uses data to justify decisions"],
            "boundary_markers": ["deflects personal questions with humor"],
        },
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
    doc = {
        "schema_version": "1.0",
        "source_type": "wechat_csv",
        "context_label": context,
        "twin_slug": slug,
        "imported_at": "2026-04-05T00:00:00+00:00",
        "source_file": "test.csv",
        "scrub_stats": {},
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    out = knowledge_dir / filename
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _patch_anthropic(response_dict: dict):
    """返回正确的 patch 上下文管理器，模拟 behavioral_extractor 中的 _anthropic。"""
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]
    mock_resp.content[0].text = json.dumps(response_dict)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp
    mock_anthropic_module = MagicMock()
    mock_anthropic_module.Anthropic.return_value = mock_client
    return patch("tools.behavioral_extractor._anthropic", mock_anthropic_module)


# ─────────────────────────────────────────────────────────────────────────────
# TestValidateNoRawText — 单元测试 validate_no_raw_text()
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateNoRawText:
    """测试 validate_no_raw_text() 函数的各种场景。"""

    def test_clean_behavioral_text_passes(self) -> None:
        """纯行为描述文本应返回空违规列表。"""
        text = (
            "tends to use indirect communication, avoids confrontation, "
            "prefers diplomatic language in professional settings"
        )
        violations = validate_no_raw_text(text)
        assert violations == []

    def test_long_quoted_string_violation(self) -> None:
        """超过 30 字符的引号字符串应被检测为违规。"""
        # 引号内字符串长度 > 30
        text = '"这是一段很长的引用文本，包含了超过三十个字符的内容，应当被检测为违规"'
        violations = validate_no_raw_text(text)
        assert len(violations) > 0
        assert any("引号" in v or "原文" in v for v in violations)

    def test_long_english_quoted_string_violation(self) -> None:
        """英文长引号字符串（>30 字符）也应被检测为违规。"""
        text = '"This is a very long quoted string that exceeds thirty characters"'
        violations = validate_no_raw_text(text)
        assert len(violations) > 0

    def test_short_quote_not_flagged(self) -> None:
        """短引号字符串（<30 字符）不应被标记为违规。"""
        text = '"He said that yesterday"'
        violations = validate_no_raw_text(text)
        # 短引用不触发长引号规则（该字符串 < 30 字符）
        assert not any("引号" in v for v in violations)

    def test_unredacted_phone_violation(self) -> None:
        """未脱敏的中国手机号应触发违规。"""
        text = "联系方式是 13812345678，请拨打"
        violations = validate_no_raw_text(text)
        assert len(violations) > 0
        assert any("手机号" in v for v in violations)

    def test_unredacted_email_violation(self) -> None:
        """未脱敏的电子邮箱应触发违规。"""
        text = "发送邮件到 user@example.com 即可"
        violations = validate_no_raw_text(text)
        assert len(violations) > 0
        assert any("邮箱" in v for v in violations)

    def test_abstraction_tags_pass(self) -> None:
        """抽象化标签文本不应触发任何违规。"""
        text = "[RELATIONSHIP_CONFLICT: financial disagreement with partner]"
        violations = validate_no_raw_text(text)
        assert violations == []

    def test_existing_placeholders_pass(self) -> None:
        """现有 PII 占位符应正常通过，不触发违规。"""
        text = "discussed [PHONE] sharing and [EMAIL] contacts with [NAME]"
        violations = validate_no_raw_text(text)
        assert violations == []

    def test_chinese_behavioral_text_passes(self) -> None:
        """中文行为描述文本（无引号/PII）应通过。"""
        text = "倾向于使用间接沟通方式，避免正面冲突，善于在团队中建立共识"
        violations = validate_no_raw_text(text)
        assert violations == []

    def test_multiple_violations_detected(self) -> None:
        """同时包含手机号和邮箱的文本应返回多个违规。"""
        text = "手机：13812345678，邮箱：test@example.com"
        violations = validate_no_raw_text(text)
        assert len(violations) >= 2

    def test_empty_string_passes(self) -> None:
        """空字符串不应触发任何违规。"""
        violations = validate_no_raw_text("")
        assert violations == []

    def test_curly_quotes_long_string_violation(self) -> None:
        """弯引号包裹的长字符串（> 30 字符）也应被检测。"""
        # 使用 Unicode 弯引号 \u201c 和 \u201d
        text = "\u201cThis is a very long quoted string exceeding thirty characters\u201d"
        violations = validate_no_raw_text(text)
        assert len(violations) > 0


# ─────────────────────────────────────────────────────────────────────────────
# TestIntegrationExtractAndValidate — 端到端集成测试
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegrationExtractAndValidate:
    """端到端集成测试：从 knowledge/ JSON 到 extractions/ 制品的完整流水线。"""

    def test_full_pipeline_produces_valid_artifact(self, tmp_path: Path) -> None:
        """完整流水线：创建夹具 -> 模拟 LLM -> 提取 -> 验证磁盘文件结构正确。"""
        slug = "test-twin"
        context = "coworker"
        chunks = [
            {"id": 0, "text": "擅长产品管理，经常使用数据驱动决策", "metadata": {}},
            {"id": 1, "text": "沟通风格直接，偏好简短消息", "metadata": {}},
            {"id": 2, "text": "技术背景深厚，经常引用第一性原理", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        valid_response = _make_valid_extraction_response()

        with _patch_anthropic(valid_response):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        # 验证文件存在
        assert output_path.exists()
        assert output_path.name == "coworker.json"

        # 加载并用 Pydantic 验证
        data = json.loads(output_path.read_text(encoding="utf-8"))
        artifact = ExtractionArtifact.model_validate(data)

        # 验证元数据字段
        assert artifact.schema_version == "2.0"
        assert artifact.context_label == "coworker"
        assert artifact.twin_slug == slug
        assert artifact.chunk_count == 3
        assert artifact.source_language == "zh"

        # 验证四个维度存在
        assert artifact.tone_style is not None
        assert artifact.vocabulary is not None
        assert artifact.knowledge_boundaries is not None
        assert artifact.behavioral_limits is not None

    def test_output_file_has_no_raw_text_violations(self, tmp_path: Path) -> None:
        """输出制品序列化后，逐字段检验无原始文本违规。"""
        slug = "test-twin"
        context = "coworker"
        chunks = [{"id": 0, "text": "工作风格高效，注重细节", "metadata": {}}]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))

        # 对每个叶子字符串值单独运行原始文本检测
        def collect_strings(obj: object) -> list[str]:
            strings: list[str] = []
            if isinstance(obj, str):
                strings.append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    strings.extend(collect_strings(item))
            elif isinstance(obj, dict):
                for v in obj.values():
                    strings.extend(collect_strings(v))
            return strings

        all_strings = collect_strings(data)
        for s in all_strings:
            violations = validate_no_raw_text(s)
            assert violations == [], f"字段值 {s!r} 包含原始文本违规：{violations}"

    def test_chunk_count_matches_input(self, tmp_path: Path) -> None:
        """输出制品的 chunk_count 与输入文件中的块数一致。"""
        slug = "test-twin"
        context = "coworker"
        chunks = [
            {"id": 0, "text": "第一块", "metadata": {}},
            {"id": 1, "text": "第二块", "metadata": {}},
            {"id": 2, "text": "第三块", "metadata": {}},
            {"id": 3, "text": "第四块", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["chunk_count"] == 4

    def test_english_input_produces_en_artifact(self, tmp_path: Path) -> None:
        """英文输入数据应生成 source_language='en' 的制品。"""
        slug = "test-twin"
        context = "partner"
        chunks = [
            {"id": 0, "text": "Great at negotiating business deals", "metadata": {}},
            {"id": 1, "text": "Prefers direct communication style", "metadata": {}},
        ]
        _write_knowledge_fixture(tmp_path, slug, context, chunks)

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["source_language"] == "en"

    def test_artifact_passes_pydantic_model_validate(self, tmp_path: Path) -> None:
        """输出文件内容应能通过 ExtractionArtifact.model_validate() 验证。"""
        slug = "test-twin"
        context = "coworker"
        _write_knowledge_fixture(
            tmp_path, slug, context,
            [{"id": 0, "text": "处理冲突时偏向协作而非对抗", "metadata": {}}]
        )

        with _patch_anthropic(_make_valid_extraction_response()):
            from tools.behavioral_extractor import extract_context
            output_path = extract_context(slug, context, tmp_path)

        raw_data = json.loads(output_path.read_text(encoding="utf-8"))
        # 不应抛出异常
        artifact = ExtractionArtifact.model_validate(raw_data)
        assert isinstance(artifact, ExtractionArtifact)
