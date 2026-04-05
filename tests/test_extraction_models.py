"""
Pydantic v2 提取模型测试 — 验证 ExtractionArtifact 及子模型的校验行为。

测试说明：
- 使用 model_validate() 测试合法和非法数据
- 验证 validate_no_raw_quotes 拒绝包含原始引用文本的制品
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tools.extraction_models import (
    BehavioralLimits,
    ExtractionArtifact,
    KnowledgeBoundaries,
    ToneStyle,
    VocabularyPatterns,
    validate_no_raw_text,
)


# ─────────────────────────────────────────────────────────────────────────────
# 辅助数据：合法的最小数据字典
# ─────────────────────────────────────────────────────────────────────────────

VALID_TONE_STYLE = {
    "formality_level": 3,
    "humor_style": "sarcastic",
    "directness": "direct",
    "emoji_habit": "rare",
    "cadence": "fast",
}

VALID_VOCABULARY = {
    "catchphrases": ["没问题", "搞定"],
    "sentence_structure": "short and punchy",
    "filler_words": ["嗯", "那个"],
    "domain_terms": ["OKR", "迭代"],
}

VALID_KNOWLEDGE_BOUNDARIES = {
    "strong_domains": ["product management", "tech strategy"],
    "avoided_topics": ["personal finance details"],
    "depth_signals": ["often references first-principles thinking"],
}

VALID_BEHAVIORAL_LIMITS = {
    "hard_nos": ["never shares salary publicly"],
    "conflict_style": "avoids direct confrontation",
    "decision_patterns": ["uses data to justify decisions"],
    "boundary_markers": ["deflects personal questions with humor"],
}

VALID_ARTIFACT = {
    "schema_version": "1.0",
    "twin_slug": "test-twin",
    "context_label": "coworker",
    "source_language": "zh",
    "extracted_at": "2026-04-05T00:00:00+00:00",
    "chunk_count": 10,
    "tone_style": VALID_TONE_STYLE,
    "vocabulary": VALID_VOCABULARY,
    "knowledge_boundaries": VALID_KNOWLEDGE_BOUNDARIES,
    "behavioral_limits": VALID_BEHAVIORAL_LIMITS,
}


class TestExtractionArtifactValid:
    """测试合法数据通过 ExtractionArtifact.model_validate()。"""

    def test_full_valid_artifact(self):
        """完整合法数据应成功通过验证。"""
        artifact = ExtractionArtifact.model_validate(VALID_ARTIFACT)
        assert artifact.twin_slug == "test-twin"
        assert artifact.context_label == "coworker"
        assert artifact.chunk_count == 10

    def test_tone_style_nested_model(self):
        """ToneStyle 子模型应正确填充。"""
        artifact = ExtractionArtifact.model_validate(VALID_ARTIFACT)
        assert artifact.tone_style.formality_level == 3
        assert artifact.tone_style.directness == "direct"

    def test_vocabulary_nested_model(self):
        """VocabularyPatterns 子模型应正确填充。"""
        artifact = ExtractionArtifact.model_validate(VALID_ARTIFACT)
        assert "没问题" in artifact.vocabulary.catchphrases

    def test_knowledge_boundaries_nested_model(self):
        """KnowledgeBoundaries 子模型应正确填充。"""
        artifact = ExtractionArtifact.model_validate(VALID_ARTIFACT)
        assert "product management" in artifact.knowledge_boundaries.strong_domains

    def test_behavioral_limits_nested_model(self):
        """BehavioralLimits 子模型应正确填充。"""
        artifact = ExtractionArtifact.model_validate(VALID_ARTIFACT)
        assert artifact.behavioral_limits.conflict_style == "avoids direct confrontation"

    def test_humor_style_optional(self):
        """humor_style 是可选字段，应接受 None。"""
        data = {**VALID_ARTIFACT, "tone_style": {**VALID_TONE_STYLE, "humor_style": None}}
        artifact = ExtractionArtifact.model_validate(data)
        assert artifact.tone_style.humor_style is None

    def test_minimal_lists_accepted(self):
        """空列表作为列表字段值应被接受。"""
        data = {
            **VALID_ARTIFACT,
            "vocabulary": {
                **VALID_VOCABULARY,
                "catchphrases": [],
                "filler_words": [],
                "domain_terms": [],
            },
        }
        artifact = ExtractionArtifact.model_validate(data)
        assert artifact.vocabulary.catchphrases == []


class TestValidationRejects:
    """测试非法数据被 ExtractionArtifact.model_validate() 拒绝。"""

    def test_missing_tone_style_raises(self):
        """缺少 tone_style 字段应引发 ValidationError。"""
        data = {k: v for k, v in VALID_ARTIFACT.items() if k != "tone_style"}
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_missing_vocabulary_raises(self):
        """缺少 vocabulary 字段应引发 ValidationError。"""
        data = {k: v for k, v in VALID_ARTIFACT.items() if k != "vocabulary"}
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_missing_knowledge_boundaries_raises(self):
        """缺少 knowledge_boundaries 字段应引发 ValidationError。"""
        data = {k: v for k, v in VALID_ARTIFACT.items() if k != "knowledge_boundaries"}
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_missing_behavioral_limits_raises(self):
        """缺少 behavioral_limits 字段应引发 ValidationError。"""
        data = {k: v for k, v in VALID_ARTIFACT.items() if k != "behavioral_limits"}
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_formality_level_string_raises(self):
        """formality_level 为字符串而非整数应引发 ValidationError。"""
        data = {
            **VALID_ARTIFACT,
            "tone_style": {**VALID_TONE_STYLE, "formality_level": "high"},
        }
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_chunk_count_string_raises(self):
        """chunk_count 为字符串应引发 ValidationError。"""
        data = {**VALID_ARTIFACT, "chunk_count": "ten"}
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_missing_twin_slug_raises(self):
        """缺少 twin_slug 应引发 ValidationError。"""
        data = {k: v for k, v in VALID_ARTIFACT.items() if k != "twin_slug"}
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)

    def test_nested_list_field_not_string_raises(self):
        """catchphrases 传入字符串而非列表应引发 ValidationError。"""
        data = {
            **VALID_ARTIFACT,
            "vocabulary": {**VALID_VOCABULARY, "catchphrases": "没问题"},
        }
        with pytest.raises(ValidationError):
            ExtractionArtifact.model_validate(data)


class TestSubModelValidation:
    """测试各子模型的独立验证。"""

    def test_tone_style_minimal_valid(self):
        """ToneStyle 最小合法数据应通过验证。"""
        ts = ToneStyle.model_validate({
            "formality_level": 1,
            "directness": "indirect",
            "emoji_habit": "frequent",
            "cadence": "slow",
        })
        assert ts.formality_level == 1

    def test_vocabulary_minimal_valid(self):
        """VocabularyPatterns 最小合法数据应通过验证。"""
        vp = VocabularyPatterns.model_validate({
            "catchphrases": [],
            "sentence_structure": "varied",
            "filler_words": [],
            "domain_terms": [],
        })
        assert vp.sentence_structure == "varied"

    def test_knowledge_boundaries_minimal_valid(self):
        """KnowledgeBoundaries 最小合法数据应通过验证。"""
        kb = KnowledgeBoundaries.model_validate({
            "strong_domains": [],
            "avoided_topics": [],
            "depth_signals": [],
        })
        assert kb.strong_domains == []

    def test_behavioral_limits_minimal_valid(self):
        """BehavioralLimits 最小合法数据应通过验证。"""
        bl = BehavioralLimits.model_validate({
            "hard_nos": [],
            "conflict_style": "collaborative",
            "decision_patterns": [],
            "boundary_markers": [],
        })
        assert bl.conflict_style == "collaborative"

    def test_tone_style_formality_required(self):
        """ToneStyle 缺少 formality_level 应引发 ValidationError。"""
        with pytest.raises(ValidationError):
            ToneStyle.model_validate({
                "directness": "direct",
                "emoji_habit": "rare",
                "cadence": "fast",
            })


class TestNoRawQuotes:
    """测试 validate_no_raw_quotes model_validator 拒绝包含长引号字符串的制品。"""

    def test_long_quoted_string_in_catchphrase_rejected(self):
        """catchphrases 中包含超过 30 字符的引用字符串应被拒绝。"""
        # Inner string must be >30 characters; Chinese chars count as 1 each
        long_quote = '"' + "这是一段非常长的直接引用文本，超过了三十个字符的限制，还需要更多内容" + '"'
        assert len(long_quote) > 32  # sanity check
        data = {
            **VALID_ARTIFACT,
            "vocabulary": {**VALID_VOCABULARY, "catchphrases": [long_quote]},
        }
        with pytest.raises((ValidationError, ValueError)):
            ExtractionArtifact.model_validate(data)

    def test_short_quoted_string_accepted(self):
        """短引号字符串（≤30 字符）应被接受。"""
        short_quote = '"短引用"'
        data = {
            **VALID_ARTIFACT,
            "vocabulary": {**VALID_VOCABULARY, "catchphrases": [short_quote]},
        }
        # Should NOT raise
        artifact = ExtractionArtifact.model_validate(data)
        assert short_quote in artifact.vocabulary.catchphrases

    def test_long_quoted_string_in_conflict_style_rejected(self):
        """conflict_style 字段包含超过 30 字符的引用字符串应被拒绝。"""
        long_quote = '"他说：这件事情根本就不是我的责任，你们不要推卸给我，我已经说了很多次了"'
        data = {
            **VALID_ARTIFACT,
            "behavioral_limits": {**VALID_BEHAVIORAL_LIMITS, "conflict_style": long_quote},
        }
        with pytest.raises((ValidationError, ValueError)):
            ExtractionArtifact.model_validate(data)

    def test_curly_quote_long_string_rejected(self):
        """弯引号包裹的超过 30 字符引用字符串应被拒绝。"""
        long_quote = "\u201c" + "这也是一段非常长的直接引用文本，超过了三十个字符，还需要更多文字才够" + "\u201d"
        data = {
            **VALID_ARTIFACT,
            "vocabulary": {**VALID_VOCABULARY, "catchphrases": [long_quote]},
        }
        with pytest.raises((ValidationError, ValueError)):
            ExtractionArtifact.model_validate(data)


class TestValidateNoRawTextFunction:
    """测试模块级 validate_no_raw_text() 工具函数。"""

    def test_clean_text_returns_empty(self):
        """干净文本应返回空违规列表。"""
        violations = validate_no_raw_text("这是正常的描述性文字")
        assert violations == []

    def test_long_quoted_string_returns_violation(self):
        """超过 30 字符的引号字符串应返回违规信息。"""
        text = '"' + "这是一段非常长的直接引用文本，超过了三十个字符的限制，还需要更多内容" + '"'
        violations = validate_no_raw_text(text)
        assert len(violations) > 0

    def test_unredacted_phone_returns_violation(self):
        """未脱敏的手机号应返回违规信息。"""
        violations = validate_no_raw_text("联系13812345678")
        assert len(violations) > 0

    def test_unredacted_email_returns_violation(self):
        """未脱敏的邮箱地址应返回违规信息。"""
        violations = validate_no_raw_text("发到test@example.com")
        assert len(violations) > 0
