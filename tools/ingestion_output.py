"""
数据导入输出模块 — 统一的 JSON 文档写入和关系标签验证。

用法示例：
    from tools.ingestion_output import write_ingestion_json, validate_context_label

    label = validate_context_label("partner")
    output_path = write_ingestion_json(
        chunks=[{"id": 0, "text": "你好", "metadata": {}}],
        source_type="wechat_csv",
        context_label=label,
        twin_slug="jiachen",
        source_file="export.csv",
        scrub_stats={"[PHONE]": 1},
    )
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────────────────────

BUILTIN_LABELS: set[str] = {"coworker", "partner", "family", "friend"}

SCHEMA_VERSION: str = "1.0"


# ─────────────────────────────────────────────────────────────────────────────
# 标签验证
# ─────────────────────────────────────────────────────────────────────────────

def validate_context_label(label: str) -> str:
    """验证关系标签并返回规范化形式。

    内置标签（coworker/partner/family/friend）和自定义标签均被接受。
    空字符串视为致命错误，打印错误信息后退出。

    Args:
        label: 用户提供的关系标签，来自 --context 参数。

    Returns:
        规范化后的标签（小写，去除首尾空白）。
    """
    label = label.strip().lower()
    if not label:
        print("错误：--context 标签不能为空", file=sys.stderr)
        sys.exit(1)
    return label


# ─────────────────────────────────────────────────────────────────────────────
# JSON 文档写入
# ─────────────────────────────────────────────────────────────────────────────

def write_ingestion_json(
    chunks: list[dict],
    source_type: str,
    context_label: str,
    twin_slug: str,
    source_file: str,
    scrub_stats: dict,
    base_dir: Path = Path("./twins"),
) -> Path:
    """将脱敏后的文本块写入结构化 JSON 文档。

    输出路径遵循 D-08 规范：
        {base_dir}/{twin_slug}/knowledge/{context_label}/{source_type}_{timestamp}.json

    Args:
        chunks: 文本块列表，每项包含 id、text、metadata 字段。
        source_type: 数据来源类型，如 "wechat_csv"、"email"、"pdf"。
        context_label: 关系标签，如 "partner"、"coworker"。
        twin_slug: 数字分身的唯一标识符。
        source_file: 原始文件名（仅用于记录，不读取文件内容）。
        scrub_stats: PII 替换统计，如 {"[PHONE]": 2}。
        base_dir: twins 根目录，默认 ./twins。

    Returns:
        写入的 JSON 文件路径。
    """
    output_dir = Path(base_dir) / twin_slug / "knowledge" / context_label
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{source_type}_{timestamp}.json"
    output_path = output_dir / filename

    doc = {
        "schema_version": SCHEMA_VERSION,
        "source_type": source_type,
        "context_label": context_label,
        "twin_slug": twin_slug,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source_file,
        "scrub_stats": scrub_stats,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    output_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入：{output_path}")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# 公共 CLI 参数（供所有解析器共享）
# ─────────────────────────────────────────────────────────────────────────────

def add_common_args(parser: argparse.ArgumentParser) -> None:
    """向 ArgumentParser 添加所有数据导入工具共用的 CLI 参数。

    每个解析器在构建参数解析器时调用此函数，以保证标志一致性（D-06）。

    Args:
        parser: 待扩展的 ArgumentParser 实例。
    """
    parser.add_argument(
        "--context",
        required=True,
        help="关系标签 (coworker/partner/family/friend/自定义)",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="数字分身的 slug 标识",
    )
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 基础目录",
    )
    parser.add_argument(
        "--use-llm-fallback",
        action="store_true",
        help="启用 LLM 脱敏（实验性）",
    )
