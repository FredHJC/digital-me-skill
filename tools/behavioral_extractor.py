"""
行为特征提取器 — 读取知识目录中的文本块，调用 LLM 提取四维行为模式，
验证输出并写入 extractions/{context}.json。

用法示例：
    python3 tools/behavioral_extractor.py --slug jiachen --context coworker --base-dir ./twins

    # 使用自定义模型：
    DIGITAL_ME_EXTRACT_MODEL=claude-opus-4-5 python3 tools/behavioral_extractor.py ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# 可选依赖：anthropic SDK
# ─────────────────────────────────────────────────────────────────────────────

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None  # type: ignore[assignment]

# 导入提取模型
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.extraction_models import ExtractionArtifact, validate_no_raw_text

# 从 pydantic 导入 ValidationError
from pydantic import ValidationError

# ─────────────────────────────────────────────────────────────────────────────
# 提示模板（延迟加载，模块首次调用时读取）
# ─────────────────────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT: Optional[str] = None


def _load_prompt_template() -> str:
    """读取 behavioral_extraction.md 提示模板（带缓存）。"""
    global _EXTRACTION_PROMPT
    if _EXTRACTION_PROMPT is None:
        prompt_path = (
            Path(__file__).resolve().parent.parent / "prompts" / "behavioral_extraction.md"
        )
        _EXTRACTION_PROMPT = prompt_path.read_text(encoding="utf-8")
    return _EXTRACTION_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _load_all_chunks(knowledge_dir: Path) -> list[dict]:
    """从知识目录中加载所有 JSON 文件的文本块，合并为扁平列表。

    Args:
        knowledge_dir: 包含知识 JSON 文件的目录路径。

    Returns:
        所有文件中所有文本块的合并列表。
    """
    all_chunks: list[dict] = []
    for json_file in sorted(knowledge_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            chunks = data.get("chunks", [])
            all_chunks.extend(chunks)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"警告：无法读取 {json_file}：{exc}", file=sys.stderr)
    return all_chunks


def _detect_language(chunks: list[dict]) -> str:
    """通过启发式方法检测数据块的主要语言。

    检测 CJK 字符（\\u4e00-\\u9fff）占比，超过 30% 则判断为中文。

    Args:
        chunks: 文本块列表，每块包含 "text" 字段。

    Returns:
        "zh"（中文）、"en"（英文）或 "mixed"（混合）。
    """
    all_text = " ".join(chunk.get("text", "") for chunk in chunks)
    if not all_text:
        return "en"

    cjk_count = sum(1 for c in all_text if "\u4e00" <= c <= "\u9fff")
    total_non_space = sum(1 for c in all_text if not c.isspace())
    if total_non_space == 0:
        return "en"

    cjk_ratio = cjk_count / total_non_space
    if cjk_ratio > 0.3:
        return "zh"
    elif cjk_count > 0:
        return "mixed"
    else:
        return "en"


def _strip_markdown_fences(text: str) -> str:
    """剥离 LLM 响应中的 markdown 代码围栏。

    Args:
        text: 待处理的 LLM 响应文本。

    Returns:
        去除围栏后的纯文本。
    """
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


def _collect_leaf_strings(obj: object) -> list[str]:
    """递归收集嵌套字典/列表结构中所有叶子字符串值。

    用于对提取制品的每个字段值单独执行原始文本检测，
    避免对整体 JSON 序列化文本检测时引号包裹造成的误报。

    Args:
        obj: 待遍历的对象（dict、list、str 或其他）。

    Returns:
        所有字符串叶子值的列表。
    """
    strings: list[str] = []
    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(_collect_leaf_strings(item))
    elif isinstance(obj, dict):
        for value in obj.values():
            strings.extend(_collect_leaf_strings(value))
    return strings


def _call_extraction_llm(chunks_text: str, context_label: str) -> str:
    """调用 Anthropic LLM 对文本块进行行为特征提取。

    使用 behavioral_extraction.md 提示模板，将 {chunks} 和 {context_label}
    替换为实际值后发送给 Claude 进行提取。

    Args:
        chunks_text: 所有文本块拼接后的字符串。
        context_label: 关系上下文标签（如 "coworker"）。

    Returns:
        LLM 返回的原始 JSON 字符串（已剥离 markdown 围栏）。
    """
    if _anthropic is None:
        print("错误：anthropic 包未安装，请运行 pip install anthropic", file=sys.stderr)
        sys.exit(1)

    prompt_template = _load_prompt_template()
    prompt = prompt_template.replace("{chunks}", chunks_text).replace("{context_label}", context_label)

    model = os.environ.get("DIGITAL_ME_EXTRACT_MODEL", "claude-sonnet-4-5")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.content[0].text.strip()
        return _strip_markdown_fences(raw_text)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"错误：LLM 提取调用失败：{exc}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────────────────────

def extract_context(slug: str, context: str, base_dir: Path) -> Path:
    """对指定关系上下文的数据块执行行为提取，写入 extractions/{context}.json。

    流程：
    1. 验证知识目录存在
    2. 加载所有文本块
    3. 检测源语言
    4. 调用 LLM 提取四维行为模式
    5. 注入元数据
    6. 运行后提取原始文本检测
    7. Pydantic 验证
    8. 写入输出文件

    Args:
        slug: 数字分身的唯一标识符。
        context: 关系上下文标签（如 "coworker"、"partner"）。
        base_dir: twins 根目录路径。

    Returns:
        写入的 JSON 文件路径（{base_dir}/{slug}/extractions/{context}.json）。
    """
    # 1. 验证知识目录
    knowledge_dir = Path(base_dir) / slug / "knowledge" / context
    if not knowledge_dir.exists():
        print(f"错误：未找到上下文数据：{knowledge_dir}", file=sys.stderr)
        sys.exit(1)

    # 2. 加载所有文本块
    all_chunks = _load_all_chunks(knowledge_dir)
    if not all_chunks:
        print("错误：上下文目录中没有数据", file=sys.stderr)
        sys.exit(1)

    # 3. 检测源语言
    source_language = _detect_language(all_chunks)

    # 4. 拼接文本块并调用 LLM
    chunks_text = "\n---\n".join(chunk.get("text", "") for chunk in all_chunks)
    raw_output = _call_extraction_llm(chunks_text, context)

    # 5. 解析 JSON
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        print(f"错误：LLM 返回无效 JSON：{exc}", file=sys.stderr)
        sys.exit(1)

    # 6. 注入元数据
    data["schema_version"] = "2.0"
    data["twin_slug"] = slug
    data["context_label"] = context
    data["source_language"] = source_language
    data["extracted_at"] = datetime.now(timezone.utc).isoformat()
    data["chunk_count"] = len(all_chunks)

    # 7. 运行后提取原始文本检测
    # 对每个字符串字段值单独检测，而非对整个 JSON 序列化文本检测
    # （JSON 序列化会将所有值用双引号包裹，造成误报）
    all_string_violations: list[str] = []
    for field_value in _collect_leaf_strings(data):
        field_violations = validate_no_raw_text(field_value)
        for v in field_violations:
            if v not in all_string_violations:
                all_string_violations.append(v)
    if all_string_violations:
        print(f"错误：提取结果包含疑似原始文本：{all_string_violations}", file=sys.stderr)
        sys.exit(1)

    # 8. Pydantic 验证
    try:
        artifact = ExtractionArtifact.model_validate(data)
    except ValidationError as exc:
        print(f"错误：提取结果不符合预期结构：{exc}", file=sys.stderr)
        sys.exit(1)

    # 9. 写入输出文件
    output_dir = Path(base_dir) / slug / "extractions"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{context}.json"
    output_path.write_text(
        json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已提取行为特征：{output_path}")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """命令行入口 — 解析参数并调用 extract_context()。"""
    parser = argparse.ArgumentParser(
        description="从知识目录中提取行为特征，写入 extractions/{context}.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 tools/behavioral_extractor.py --slug jiachen --context coworker --base-dir ./twins
  DIGITAL_ME_EXTRACT_MODEL=claude-opus-4-5 python3 tools/behavioral_extractor.py --slug jiachen --context partner
""",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="数字分身的 slug 标识",
    )
    parser.add_argument(
        "--context",
        required=True,
        help="关系标签 (coworker/partner/family/friend/自定义)",
    )
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 基础目录（默认：./twins）",
    )
    args = parser.parse_args()
    extract_context(args.slug, args.context, Path(args.base_dir))


if __name__ == "__main__":
    main()
