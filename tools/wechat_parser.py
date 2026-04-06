"""
WeChat 聊天记录解析器 — 解析 WeChatMsg 导出的 CSV 文件。

用法示例：
    python3 tools/wechat_parser.py \\
        --file wechat_export.csv \\
        --context partner \\
        --slug my-twin

仅处理用户本人发出的文本消息（IsSender=1, Type=1），自动脱敏后写入 JSON。
"""
from __future__ import annotations

import csv
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pii_scrubber import scrub
from tools.ingestion_output import validate_context_label, write_ingestion_json, add_common_args

# ─────────────────────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS: set[str] = {"StrTalker", "StrContent", "Type", "CreateTime", "IsSender"}


# ─────────────────────────────────────────────────────────────────────────────
# 解析函数
# ─────────────────────────────────────────────────────────────────────────────

def parse_wechat_csv(
    file_path: Path,
    use_llm_fallback: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    """解析 WeChatMsg 导出的 CSV 文件，提取用户发送的文本消息并脱敏。

    Args:
        file_path: WeChatMsg 导出的 CSV 文件路径。
        use_llm_fallback: 是否启用 LLM 脱敏回退。

    Returns:
        (chunks, combined_stats)
        chunks: 脱敏后的文本块列表，每项含 id、text、metadata。
        combined_stats: 各 PII 占位符的累计替换计数。
    """
    chunks: list[dict] = []
    combined_stats: dict[str, int] = {}

    with open(file_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        # 列名校验：提前失败并打印实际列名以便调试
        actual_columns = set(reader.fieldnames or [])
        if not REQUIRED_COLUMNS.issubset(actual_columns):
            print(
                f"错误：CSV 缺少必要列。期望: {REQUIRED_COLUMNS}，实际: {reader.fieldnames}",
                file=sys.stderr,
            )
            sys.exit(1)

        for row in reader:
            # 仅处理文本消息（Type=1）且由本人发出（IsSender=1）
            if row.get("Type") != "1" or row.get("IsSender") != "1":
                continue

            content = row.get("StrContent", "").strip()
            if not content:
                continue

            # PII 脱敏
            scrubbed_text, msg_stats = scrub(content, use_llm_fallback=use_llm_fallback)

            # 累积脱敏统计
            for key, count in msg_stats.items():
                combined_stats[key] = combined_stats.get(key, 0) + count

            # 时间戳转换：Unix 时间戳 -> ISO 8601
            try:
                iso_ts = datetime.fromtimestamp(
                    int(row.get("CreateTime", 0)), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                iso_ts = ""

            chunk = {
                "id": len(chunks),
                "text": scrubbed_text,
                "metadata": {
                    "timestamp": iso_ts,
                    "sender": "self",
                    "message_type": "text",
                    "talker": row.get("StrTalker", ""),
                },
            }
            chunks.append(chunk)

    if not chunks:
        print(
            "警告：解析了 0 条用户发送的文本消息。请检查 CSV 格式。",
            file=sys.stderr,
        )

    return chunks, combined_stats


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 主入口：解析参数、调用解析器、写入 JSON。"""
    parser = argparse.ArgumentParser(
        description="WeChat 聊天记录解析器（WeChatMsg CSV 格式）"
    )
    parser.add_argument(
        "--file",
        required=True,
        type=str,
        help="WeChatMsg 导出的 CSV 文件路径",
    )
    add_common_args(parser)

    args = parser.parse_args()

    # 文件存在性校验（路径规范化，防止路径穿越）
    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"错误：文件不存在：{file_path}", file=sys.stderr)
        sys.exit(1)

    context = validate_context_label(args.context)

    chunks, combined_stats = parse_wechat_csv(
        file_path, use_llm_fallback=args.use_llm_fallback
    )

    write_ingestion_json(
        chunks=chunks,
        source_type="wechat_csv",
        context_label=context,
        twin_slug=args.slug,
        source_file=str(file_path),
        scrub_stats=combined_stats,
        base_dir=Path(args.base_dir),
    )


if __name__ == "__main__":
    main()
