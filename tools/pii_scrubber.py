"""
PII 脱敏模块 — 对文本中的个人敏感信息进行检测和替换。

用法示例：
    from tools.pii_scrubber import scrub, PLACEHOLDER_TYPES

    text, stats = scrub("手机号13812345678，邮箱test@example.com")
    # text: "手机号[PHONE]，邮箱[EMAIL]"
    # stats: {"[PHONE]": 1, "[EMAIL]": 1}

    # 启用 LLM 上下文脱敏（需要 ANTHROPIC_API_KEY）
    text, stats = scrub("昨天和老婆吵了一架", use_llm_fallback=True)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# 可选依赖：anthropic SDK
# ─────────────────────────────────────────────────────────────────────────────

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]

# ─────────────────────────────────────────────────────────────────────────────
# 提示模板（延迟加载，模块首次调用时读取）
# ─────────────────────────────────────────────────────────────────────────────

_SCRUB_PROMPT: Optional[str] = None


def _load_scrub_prompt() -> str:
    """读取 llm_scrub.md 提示模板（带缓存）。"""
    global _SCRUB_PROMPT
    if _SCRUB_PROMPT is None:
        prompt_path = (
            Path(__file__).resolve().parent.parent / "prompts" / "llm_scrub.md"
        )
        _SCRUB_PROMPT = prompt_path.read_text(encoding="utf-8")
    return _SCRUB_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# 占位符类型列表（供下游模块参考）
# ─────────────────────────────────────────────────────────────────────────────

PLACEHOLDER_TYPES: list[str] = [
    "[NAME]",
    "[PHONE]",
    "[EMAIL]",
    "[ID_NUMBER]",
    "[ADDRESS]",
    "[DOB]",
    "[BANK_ACCOUNT]",
]

# ─────────────────────────────────────────────────────────────────────────────
# 正则表达式模式列表（顺序重要：更精确的模式在前）
# ─────────────────────────────────────────────────────────────────────────────

PATTERNS: list[tuple[str, str]] = [
    # 1. 中国居民身份证号（18 位，末位可为 X）
    #    必须在银行卡号之前，避免 18 位身份证被 16-19 位银行卡模式误匹配
    #    使用数字前后缀断言（非 \b），以兼容中文字符边界
    (r"(?<!\d)\d{17}[\dXx](?!\d)", "[ID_NUMBER]"),

    # 2. 电子邮箱
    (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "[EMAIL]"),

    # 3. 中国手机号（支持 +86 / 86 前缀）
    #    来自 ChinaMobilePhoneNumberRegex 规范；使用数字边界断言防止匹配号段内子串
    (r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)", "[PHONE]"),

    # 4. 中国固定电话（区号 + 号码）；使用数字边界断言防止匹配银行卡子串
    (r"(?<!\d)0\d{2,3}[-\s]?\d{7,8}(?!\d)", "[PHONE]"),

    # 5. 银行卡号（16-19 位；ID 号已先行替换，此处不会重复匹配）
    (r"(?<!\d)\d{16,19}(?!\d)", "[BANK_ACCOUNT]"),

    # 6. 出生日期（中文格式）：1990年1月1日 / 1990-01-01 / 1990/01/01
    #    使用数字边界断言兼容中文字符边界
    (r"(?<!\d)(?:19|20)\d{2}[-年/]\d{1,2}[-月/]\d{1,2}[日]?(?!\d)", "[DOB]"),

    # 7. 出生日期（西方格式）：MM/DD/YYYY 或 MM-DD-YYYY
    (r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b", "[DOB]"),
]


# ─────────────────────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────────────────────

def scrub(text: str, use_llm_fallback: bool = False) -> tuple[str, dict]:
    """检测并替换文本中的结构化 PII。

    Args:
        text: 待处理的原始文本。
        use_llm_fallback: 是否启用 LLM 脱敏回退（姓名、地址等模糊 PII）。
                          需要 ANTHROPIC_API_KEY 环境变量和 anthropic 包。

    Returns:
        (scrubbed_text, stats_dict)
        scrubbed_text: 已将 PII 替换为占位符的文本。
        stats_dict: 各占位符的替换计数，如 {"[PHONE]": 1, "[EMAIL]": 2}。
    """
    stats: dict[str, int] = {}
    result = text

    for pattern, placeholder in PATTERNS:
        matches = re.findall(pattern, result)
        if matches:
            count = len(matches)
            stats[placeholder] = stats.get(placeholder, 0) + count
        result = re.sub(pattern, placeholder, result)

    if use_llm_fallback:
        result, llm_stats = _llm_scrub(result)
        for key, val in llm_stats.items():
            stats[key] = stats.get(key, 0) + val

    return result, stats


def _llm_scrub(text: str) -> tuple[str, dict]:
    """LLM 上下文脱敏 — 对姓名、地址等模糊 PII 进行语义识别和抽象化。

    使用 Anthropic API 将个人叙述替换为类型化的行为标签，如：
    - [RELATIONSHIP_CONFLICT: 家庭财务争吵]
    - [HEALTH_SITUATION: 家人生病]

    Args:
        text: 已经过正则脱敏的文本（[PHONE]、[EMAIL] 等占位符应保留）。

    Returns:
        (scrubbed_text, abstractions_dict)
        scrubbed_text: 经 LLM 抽象化处理后的文本。
        abstractions_dict: 各抽象标签的使用次数，如 {"[RELATIONSHIP_CONFLICT]": 1}。
        若 API 不可用或调用失败，返回 (text, {})（非致命降级）。
    """
    # 检查 anthropic 包是否可用
    if _anthropic is None:
        print("警告：anthropic 包未安装，LLM 脱敏跳过", file=sys.stderr)
        return (text, {})

    # 检查 API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("警告：未设置 ANTHROPIC_API_KEY，LLM 脱敏跳过", file=sys.stderr)
        return (text, {})

    # 读取提示模板
    try:
        prompt_template = _load_scrub_prompt()
        prompt = prompt_template.replace("{text}", text)
    except Exception as exc:
        print(f"警告：无法加载脱敏提示模板，LLM 脱敏跳过：{exc}", file=sys.stderr)
        return (text, {})

    # 获取模型名称
    model = os.environ.get("DIGITAL_ME_SCRUB_MODEL", "claude-haiku-4-5")

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.content[0].text.strip()

        # 剥离 markdown 代码围栏
        raw_text = _strip_markdown_fences(raw_text)

        # 解析 JSON 响应
        data = json.loads(raw_text)
        scrubbed = data.get("scrubbed", text)
        abstractions = data.get("abstractions", {})
        return (scrubbed, abstractions)

    except json.JSONDecodeError as exc:
        print(f"警告：LLM 返回非 JSON 响应，脱敏跳过：{exc}", file=sys.stderr)
        return (text, {})
    except Exception as exc:
        print(f"警告：LLM 脱敏调用失败，跳过：{exc}", file=sys.stderr)
        return (text, {})


def _strip_markdown_fences(text: str) -> str:
    """剥离 LLM 响应中的 markdown 代码围栏。

    处理以下格式：
    - ```json\\n{...}\\n```
    - ```\\n{...}\\n```
    - 纯 JSON（无围栏，直接返回）

    Args:
        text: 待处理的 LLM 响应文本。

    Returns:
        去除围栏后的纯文本。
    """
    # 去除首尾空白
    text = text.strip()
    # 去除 ```json 或 ``` 开头
    if text.startswith("```"):
        # 找到第一行结束位置（跳过语言标注行）
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    # 去除末尾 ```
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()
