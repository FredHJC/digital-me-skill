"""
文本导入工具 — 将 Markdown 文件或纯文本转为脱敏后的 JSON 文档。

用法示例：
    # 从 Markdown 文件导入
    python3 tools/text_ingestor.py --file notes.md --context coworker --slug my-twin

    # 内联文本粘贴
    python3 tools/text_ingestor.py --text "你好，这是一段文字。" --context friend --slug my-twin

    # 从标准输入读取（剪贴板粘贴）
    echo "文本内容" | python3 tools/text_ingestor.py --context family --slug my-twin
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pii_scrubber import scrub
from tools.ingestion_output import validate_context_label, write_ingestion_json, add_common_args


# ─────────────────────────────────────────────────────────────────────────────
# 文本分块
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """将文本按段落拆分为不超过 chunk_size 字符的块。

    先按双换行切分段落，然后将短段落合并至接近 chunk_size，
    超长段落尝试在句末（句号/中文句号）处切分。

    Args:
        text: 待切分的原始文本。
        chunk_size: 每块目标最大字符数，默认 500。

    Returns:
        非空文本块列表（已 strip）。
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        # 段落本身超过 chunk_size：按句末切分
        if len(para) > chunk_size:
            # 先把积累的 current 作为一块提交
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0

            # 在句号处切分超长段落
            start = 0
            while start < len(para):
                end = start + chunk_size
                if end >= len(para):
                    sub = para[start:].strip()
                    if sub:
                        chunks.append(sub)
                    break

                # 向后找最近的句末标点
                split_pos = end
                for i in range(end, max(start, end - 100), -1):
                    if para[i] in ("。", "！", "？", ".", "!", "?"):
                        split_pos = i + 1
                        break

                sub = para[start:split_pos].strip()
                if sub:
                    chunks.append(sub)
                start = split_pos
        else:
            # 加入当前块
            if current_len + len(para) + 2 > chunk_size and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_len = len(para)
            else:
                current.append(para)
                current_len += len(para) + 2  # 加上分隔符长度

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if c.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# 导入函数
# ─────────────────────────────────────────────────────────────────────────────

def ingest_text(
    text: str,
    source_type: str,
    use_llm_fallback: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    """将文本切分并脱敏，返回块列表和统计。

    Args:
        text: 原始文本内容。
        source_type: 来源类型（"markdown" / "plaintext"）。
        use_llm_fallback: 是否启用 LLM 脱敏回退。

    Returns:
        (chunks, combined_stats)
        chunks: 脱敏后的文本块列表。
        combined_stats: 各 PII 占位符的累计替换计数。
    """
    raw_chunks = chunk_text(text)

    chunks: list[dict] = []
    combined_stats: dict[str, int] = {}

    for i, raw_chunk in enumerate(raw_chunks):
        scrubbed_text, chunk_stats = scrub(raw_chunk, use_llm_fallback=use_llm_fallback)

        for key, count in chunk_stats.items():
            combined_stats[key] = combined_stats.get(key, 0) + count

        chunk = {
            "id": i,
            "text": scrubbed_text,
            "metadata": {
                "source_format": source_type,
            },
        }
        chunks.append(chunk)

    return chunks, combined_stats


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 主入口：解析参数、读取文本、脱敏、写入 JSON。"""
    parser = argparse.ArgumentParser(description="文本/Markdown 导入工具")

    # 互斥输入组：--file 或 --text（不提供则从 stdin 读取）
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--file",
        type=str,
        help="Markdown (.md) 或纯文本 (.txt) 文件路径",
    )
    input_group.add_argument(
        "--text",
        type=str,
        help="内联文本（粘贴模式，INGEST-06）",
    )

    add_common_args(parser)

    args = parser.parse_args()

    context = validate_context_label(args.context)

    # 确定输入来源和 source_type
    if args.file:
        file_path = Path(args.file).resolve()
        if not file_path.exists():
            print(f"错误：文件不存在：{file_path}", file=sys.stderr)
            sys.exit(1)
        text = file_path.read_text(encoding="utf-8")
        ext = file_path.suffix.lower()
        source_type = "markdown" if ext == ".md" else "plaintext"
        source_file = str(file_path)
    elif args.text:
        text = args.text
        source_type = "plaintext"
        source_file = "inline_text"
    else:
        # 从 stdin 读取（剪贴板粘贴用例）
        text = sys.stdin.read()
        source_type = "plaintext"
        source_file = "stdin"

    if not text.strip():
        print("警告：输入文本为空，无内容可导入", file=sys.stderr)
        sys.exit(0)

    chunks, combined_stats = ingest_text(
        text, source_type, use_llm_fallback=args.use_llm_fallback
    )

    write_ingestion_json(
        chunks=chunks,
        source_type=source_type,
        context_label=context,
        twin_slug=args.slug,
        source_file=source_file,
        scrub_stats=combined_stats,
        base_dir=Path(args.base_dir),
    )


if __name__ == "__main__":
    main()
