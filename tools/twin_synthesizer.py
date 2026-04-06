"""
数字分身合成器 — 读取所有上下文的提取制品，两阶段调用 LLM 合成
core.md（跨上下文不变量）和 facets/{context}.md（各上下文专属适配）。

用法示例：
    python3 tools/twin_synthesizer.py --slug zhangsan --base-dir ./twins

    # 仅合成 core：
    python3 tools/twin_synthesizer.py --slug zhangsan --mode core

    # 合成指定上下文 facet：
    python3 tools/twin_synthesizer.py --slug zhangsan --mode facet --context coworker

    # 附加用户补充说明：
    python3 tools/twin_synthesizer.py --slug zhangsan --hints "说话风格偏学术"

    # 使用自定义模型：
    DIGITAL_ME_SYNTH_MODEL=claude-opus-4-5 python3 tools/twin_synthesizer.py --slug zhangsan
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

# ─────────────────────────────────────────────────────────────────────────────
# 工具模块导入
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.extraction_models import ExtractionArtifact, validate_no_raw_text

# ─────────────────────────────────────────────────────────────────────────────
# 提示模板（延迟加载，模块首次调用时读取）
# ─────────────────────────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT: Optional[str] = None


def _load_prompt_template() -> str:
    """读取 twin_synthesizer.md 提示模板（带缓存）。"""
    global _SYNTHESIS_PROMPT
    if _SYNTHESIS_PROMPT is None:
        prompt_path = (
            Path(__file__).resolve().parent.parent / "prompts" / "twin_synthesizer.md"
        )
        _SYNTHESIS_PROMPT = prompt_path.read_text(encoding="utf-8")
    return _SYNTHESIS_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _load_all_extractions(extractions_dir: Path) -> list[ExtractionArtifact]:
    """从 extractions/ 目录中加载所有 *.json 提取制品，按文件名排序。

    Args:
        extractions_dir: 包含提取制品 JSON 文件的目录路径。

    Returns:
        按文件名排序的 ExtractionArtifact 列表。
    """
    json_files = sorted(extractions_dir.glob("*.json"))
    if not json_files:
        print(f"错误：extractions 目录中没有提取制品：{extractions_dir}", file=sys.stderr)
        sys.exit(1)

    artifacts: list[ExtractionArtifact] = []
    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            artifact = ExtractionArtifact.model_validate(data)
            artifacts.append(artifact)
        except Exception as exc:
            print(f"警告：无法加载 {json_file}：{exc}", file=sys.stderr)
    return artifacts


def _build_prompt(
    mode: str,
    extractions: list[ExtractionArtifact],
    context_label: str = "",
    core_text: str = "",
    hints: Optional[str] = None,
) -> str:
    """构建合成提示词，替换模板中的所有占位符。

    Args:
        mode: 合成模式，"core" 或 "facet"。
        extractions: 提取制品列表（core 模式为全部，facet 模式为单个）。
        context_label: 当前上下文标签（facet 模式使用）。
        core_text: 已生成的 core.md 内容（facet 模式使用）。
        hints: 用户补充说明（可选）。

    Returns:
        填充后的完整提示词字符串。
    """
    template = _load_prompt_template()

    # {extractions_json}：core 模式传所有制品列表，facet 模式传单个制品
    if mode == "core":
        extractions_json = json.dumps(
            [a.model_dump() for a in extractions],
            ensure_ascii=False,
            indent=2,
        )
    else:
        extractions_json = json.dumps(
            extractions[0].model_dump() if extractions else {},
            ensure_ascii=False,
            indent=2,
        )

    # {context_list}：所有制品的 context_label 逗号连接
    context_list = ", ".join(a.context_label for a in extractions)

    # {hints_block}：有用户说明则使用，否则填默认文本
    hints_block = hints if hints else "（无用户补充说明）"

    prompt = (
        template
        .replace("{mode}", mode)
        .replace("{extractions_json}", extractions_json)
        .replace("{context_label}", context_label)
        .replace("{core_text}", core_text)
        .replace("{hints_block}", hints_block)
        .replace("{context_list}", context_list)
    )
    return prompt


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


def _call_synthesis_llm(prompt: str) -> str:
    """调用 Anthropic LLM 执行合成。

    使用 twin_synthesizer.md 提示模板调用 Claude，返回合成结果。
    模型通过 DIGITAL_ME_SYNTH_MODEL 环境变量配置（默认 claude-sonnet-4-5）。

    Args:
        prompt: 已填充占位符的完整提示词。

    Returns:
        LLM 返回的原始 Markdown 字符串（已剥离代码围栏）。
    """
    if _anthropic is None:
        print("错误：anthropic 包未安装，请运行 pip install anthropic", file=sys.stderr)
        sys.exit(1)

    model = os.environ.get("DIGITAL_ME_SYNTH_MODEL", "claude-sonnet-4-5")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.content[0].text.strip()
        return _strip_markdown_fences(raw_text)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"错误：LLM 合成调用失败：{exc}", file=sys.stderr)
        sys.exit(1)


def _validate_and_write(content: str, output_path: Path) -> None:
    """验证内容不含原始文本后写入文件（D-10, D-11）。

    调用 validate_no_raw_text() 检查内容。若有违规则打印错误并以 exit 1 退出。
    否则将内容写入 output_path（UTF-8 编码）。

    Args:
        content: 待写入的 Markdown 内容。
        output_path: 目标文件路径。
    """
    violations = validate_no_raw_text(content)
    if violations:
        print(
            f"错误：合成结果包含疑似原始文本，写入已终止：{violations}",
            file=sys.stderr,
        )
        sys.exit(1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def _update_meta_after_synthesis(twin_dir: Path, contexts: list[str]) -> None:
    """合成成功后更新 meta.json，写入 synthesized_at 和 synthesized_contexts。

    Args:
        twin_dir: 数字分身目录路径。
        contexts: 本次合成的上下文标签列表。
    """
    meta_path = twin_dir / "meta.json"
    if not meta_path.exists():
        print(f"警告：meta.json 不存在：{meta_path}", file=sys.stderr)
        return

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["synthesized_at"] = datetime.now(timezone.utc).isoformat()
    meta["synthesized_contexts"] = contexts
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 核心合成函数
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_core(slug: str, base_dir: Path, hints: Optional[str] = None) -> Path:
    """第一阶段：从所有上下文的提取制品合成 core.md（跨上下文不变量）。

    流程（D-03）：
    1. 加载所有提取制品
    2. 若只有 1 个上下文，打印警告
    3. 构建 core 模式提示词（含 hints）
    4. 调用 LLM 合成
    5. 验证并写入 core.md

    Args:
        slug: 数字分身的唯一标识符。
        base_dir: twins 根目录路径。
        hints: 用户补充说明（可选）。

    Returns:
        写入的 core.md 文件路径。
    """
    twin_dir = Path(base_dir) / slug
    extractions_dir = twin_dir / "extractions"

    if not extractions_dir.exists():
        print(f"错误：extractions 目录不存在：{extractions_dir}", file=sys.stderr)
        sys.exit(1)

    # 加载所有提取制品
    artifacts = _load_all_extractions(extractions_dir)

    # 单上下文警告
    if len(artifacts) == 1:
        print(
            f"警告：只有 1 个上下文的数据，core.md 将包含所有特征",
            file=sys.stderr,
        )

    # 构建提示词并调用 LLM
    prompt = _build_prompt(mode="core", extractions=artifacts, hints=hints)
    raw_output = _call_synthesis_llm(prompt)

    # 验证并写入 core.md
    output_path = twin_dir / "core.md"
    _validate_and_write(raw_output, output_path)
    print(f"已生成 core.md：{output_path}")
    return output_path


def synthesize_facet(
    slug: str,
    context: str,
    base_dir: Path,
    hints: Optional[str] = None,
) -> Path:
    """第二阶段：从单上下文提取制品 + core.md 合成 facets/{context}.md。

    流程（D-03）：
    1. 加载指定上下文的提取制品
    2. 读取已生成的 core.md
    3. 构建 facet 模式提示词
    4. 调用 LLM 合成
    5. 验证并写入 facets/{context}.md

    Args:
        slug: 数字分身的唯一标识符。
        context: 关系上下文标签（如 "coworker"）。
        base_dir: twins 根目录路径。
        hints: 用户补充说明（可选）。

    Returns:
        写入的 facets/{context}.md 文件路径。
    """
    twin_dir = Path(base_dir) / slug
    extraction_path = twin_dir / "extractions" / f"{context}.json"
    core_path = twin_dir / "core.md"

    if not extraction_path.exists():
        print(f"错误：提取制品不存在：{extraction_path}", file=sys.stderr)
        sys.exit(1)

    if not core_path.exists():
        print(f"错误：core.md 不存在，请先运行 core 合成：{core_path}", file=sys.stderr)
        sys.exit(1)

    # 加载提取制品和 core.md
    data = json.loads(extraction_path.read_text(encoding="utf-8"))
    artifact = ExtractionArtifact.model_validate(data)
    core_text = core_path.read_text(encoding="utf-8")

    # 构建提示词并调用 LLM
    prompt = _build_prompt(
        mode="facet",
        extractions=[artifact],
        context_label=context,
        core_text=core_text,
        hints=hints,
    )
    raw_output = _call_synthesis_llm(prompt)

    # 验证并写入 facets/{context}.md
    output_path = twin_dir / "facets" / f"{context}.md"
    _validate_and_write(raw_output, output_path)
    print(f"已生成 facet：{output_path}")
    return output_path


def synthesize_all(slug: str, base_dir: Path, hints: Optional[str] = None) -> None:
    """完整的两阶段合成流水线：core 合成 -> 所有上下文 facet 合成。

    流程：
    1. 加载所有提取制品，获取上下文列表
    2. 若 core.md 已存在，在合成前自动备份（D-09）
    3. 调用 synthesize_core() 生成 core.md
    4. 对每个上下文调用 synthesize_facet()
    5. 更新 meta.json

    Args:
        slug: 数字分身的唯一标识符。
        base_dir: twins 根目录路径。
        hints: 用户补充说明（可选）。
    """
    twin_dir = Path(base_dir) / slug
    extractions_dir = twin_dir / "extractions"

    if not extractions_dir.exists():
        print(f"错误：extractions 目录不存在：{extractions_dir}", file=sys.stderr)
        sys.exit(1)

    # 获取所有提取制品上下文
    artifacts = _load_all_extractions(extractions_dir)
    contexts = [a.context_label for a in artifacts]

    # 自动备份（若 core.md 已存在）
    core_path = twin_dir / "core.md"
    if core_path.exists():
        from tools.version_manager import backup  # lazy import — avoids mock contamination
        version_name = f"pre-synth-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        backup(twin_dir, version_name)

    # 第一阶段：core 合成
    synthesize_core(slug, base_dir, hints=hints)

    # 第二阶段：逐上下文 facet 合成
    for context in contexts:
        synthesize_facet(slug, context, base_dir, hints=hints)

    # 更新 meta.json
    _update_meta_after_synthesis(twin_dir, contexts)
    print(f"合成完成：{slug}（core + {len(contexts)} 个上下文）")


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """命令行入口 — 解析参数并调用相应的合成函数。"""
    parser = argparse.ArgumentParser(
        description="从提取制品合成数字分身 persona（core.md + facets/{context}.md）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 完整两阶段合成（推荐）：
  python3 tools/twin_synthesizer.py --slug zhangsan --base-dir ./twins

  # 仅合成 core（跨上下文不变量）：
  python3 tools/twin_synthesizer.py --slug zhangsan --mode core

  # 合成指定上下文的 facet：
  python3 tools/twin_synthesizer.py --slug zhangsan --mode facet --context coworker

  # 附加用户补充说明（advisory，不覆盖数据信号）：
  python3 tools/twin_synthesizer.py --slug zhangsan --hints "说话风格偏学术，喜欢举例"

  # 使用更强模型：
  DIGITAL_ME_SYNTH_MODEL=claude-opus-4-5 python3 tools/twin_synthesizer.py --slug zhangsan
""",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="数字分身的 slug 标识",
    )
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 基础目录（默认：./twins）",
    )
    parser.add_argument(
        "--hints",
        default=None,
        help="用户补充说明（advisory，不覆盖数据驱动信号，可选）",
    )
    parser.add_argument(
        "--mode",
        choices=["core", "facet", "all"],
        default="all",
        help="合成模式：core（仅 core.md）、facet（仅指定上下文）、all（完整流水线，默认）",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="关系上下文标签（仅 --mode facet 时必填）",
    )
    args = parser.parse_args()
    base_dir = Path(args.base_dir)

    if args.mode == "core":
        synthesize_core(args.slug, base_dir, hints=args.hints)
    elif args.mode == "facet":
        if not args.context:
            print("错误：--mode facet 需要同时指定 --context", file=sys.stderr)
            sys.exit(1)
        synthesize_facet(args.slug, args.context, base_dir, hints=args.hints)
    else:
        synthesize_all(args.slug, base_dir, hints=args.hints)


if __name__ == "__main__":
    main()
