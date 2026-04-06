"""
提取制品 Pydantic v2 模型 — 定义行为提取的四个维度的数据契约。

用法示例：
    from tools.extraction_models import ExtractionArtifact, validate_no_raw_text

    artifact = ExtractionArtifact.model_validate(data)
    violations = validate_no_raw_text(some_string)
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ValidationError, model_validator

# ─────────────────────────────────────────────────────────────────────────────
# 原始文本信号检测（模块级，用于 validate_no_raw_text）
# ─────────────────────────────────────────────────────────────────────────────

_RAW_TEXT_SIGNALS: list[re.Pattern] = [
    # 长引号字符串（直引号或弯引号，超过 80 字符）
    # 允许短句引用（口头禅、标志性表达 ≤80 字符），拦截长段原文
    re.compile(r'[""\u201c\u201d][^""\u201c\u201d]{80,}[""\u201c\u201d]'),
    # 未脱敏的手机号（中国格式，数字边界）
    re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"),
    # 未脱敏的电子邮箱
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
]


def validate_no_raw_text(text: str) -> list[str]:
    """检查文本是否包含疑似原始 PII 或直接引用文本。

    Args:
        text: 待检查的文本字符串。

    Returns:
        违规描述列表；若无违规则返回空列表。
    """
    violations: list[str] = []
    descriptions = [
        "包含超过 30 字符的引号字符串（疑似直接引用原文）",
        "包含未脱敏的手机号",
        "包含未脱敏的电子邮箱",
    ]
    for pattern, description in zip(_RAW_TEXT_SIGNALS, descriptions):
        if pattern.search(text):
            violations.append(description)
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数：递归收集模型中所有字符串字段值
# ─────────────────────────────────────────────────────────────────────────────

def _collect_strings(obj: object) -> list[str]:
    """递归收集嵌套模型和列表中的所有字符串值。"""
    strings: list[str] = []
    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(_collect_strings(item))
    elif isinstance(obj, BaseModel):
        for field_value in obj.__dict__.values():
            strings.extend(_collect_strings(field_value))
    return strings


# ─────────────────────────────────────────────────────────────────────────────
# 子模型：四个提取维度
# ─────────────────────────────────────────────────────────────────────────────

class ToneStyle(BaseModel):
    """语气风格维度 — 描述说话者的正式程度、幽默感、直接性、亲密度等。"""

    formality_level: int
    """正式程度，1-5 评分（1=非常随意，5=非常正式）。"""

    humor_style: Optional[str] = None
    """幽默风格描述（可选）。"""

    directness: str
    """直接性描述，如 "direct"、"indirect"、"context-dependent"。"""

    emoji_habit: str
    """表情符号使用习惯，如 "frequent"、"rare"、"never"。"""

    cadence: str
    """表达节奏，如 "fast"、"slow"、"measured"。"""

    warmth_level: str = "neutral"
    """亲密程度，如 "distant"、"neutral"、"warm"、"affectionate"。"""

    pet_names: list[str] = []
    """昵称/爱称列表，如 ["宝", "老公"]。伴侣/家人场景常见。"""


class VocabularyPatterns(BaseModel):
    """词汇模式维度 — 描述常用词汇、句式结构和领域术语。"""

    catchphrases: list[str]
    """常用口头禅或标志性用语列表。"""

    sentence_structure: str
    """句式结构描述，如 "short and punchy"、"long and elaborative"。"""

    filler_words: list[str]
    """口头填充词列表，如 ["嗯", "那个", "就是说"]。"""

    domain_terms: list[str]
    """专业领域术语列表，如 ["OKR", "迭代", "产品路线图"]。"""


class KnowledgeBoundaries(BaseModel):
    """知识边界维度 — 描述擅长领域、回避话题和深度信号。"""

    strong_domains: list[str]
    """深度掌握的专业领域列表。"""

    avoided_topics: list[str]
    """倾向于回避或不展开讨论的话题列表。"""

    depth_signals: list[str]
    """表明知识深度的行为信号列表，如 ["经常引用第一性原理"]。"""


class BehavioralPatterns(BaseModel):
    """行为模式维度 — 根据关系场景自适应的行为描述。"""

    hard_limits: list[str] = []
    """行为底线。同事: 职业红线; 伴侣: 关系边界; 家人: 家庭动态底线。"""

    conflict_style: str
    """冲突/分歧处理方式。同事: 专业争论; 伴侣: 吵架和好模式; 家人: 家庭摩擦处理。"""

    decision_patterns: list[str]
    """决策模式。同事: 工作决策; 伴侣: 共同决定; 家人: 家庭事务决策。"""

    emotional_patterns: list[str] = []
    """情感表达模式。同事: 通常克制; 伴侣: 撒娇/表达爱意方式; 家人: 关心表达方式。"""

    care_signals: list[str] = []
    """关心信号。同事: 帮助同事的方式; 伴侣: 表达爱的细节; 家人: 孝心表达。"""


# ─────────────────────────────────────────────────────────────────────────────
# 主模型：提取制品
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionArtifact(BaseModel):
    """完整的行为提取制品 — 包含四个维度的提取结果和元数据。"""

    schema_version: str
    """制品架构版本，如 "1.0"。"""

    twin_slug: str
    """数字分身的唯一标识符。"""

    context_label: str
    """关系上下文标签，如 "coworker"、"partner"、"family"。"""

    source_language: str
    """源数据语言，如 "zh"（中文）、"en"（英文）、"mixed"（混合）。"""

    extracted_at: str
    """提取时间戳（ISO 8601 格式）。"""

    chunk_count: int
    """用于提取的文本块数量。"""

    tone_style: ToneStyle
    """语气风格维度提取结果。"""

    vocabulary: VocabularyPatterns
    """词汇模式维度提取结果。"""

    knowledge_boundaries: KnowledgeBoundaries
    """知识边界维度提取结果。"""

    behavioral_patterns: BehavioralPatterns
    """行为模式维度提取结果（根据关系场景自适应）。"""

    @model_validator(mode="after")
    def validate_no_raw_quotes(self) -> "ExtractionArtifact":
        """检查制品中是否包含疑似原始引用文本（超过 80 字符的引号字符串）。

        允许标志性短句和口头禅（≤80 字符），拦截整段对话原文。

        Raises:
            ValueError: 若任何字符串字段包含超过 80 字符的引号字符串。
        """
        long_quote_pattern = re.compile(
            r'[""\u201c\u201d][^""\u201c\u201d]{80,}[""\u201c\u201d]'
        )
        all_strings = _collect_strings(self)
        for s in all_strings:
            if long_quote_pattern.search(s):
                raise ValueError("提取结果包含疑似原始引用文本")
        return self
