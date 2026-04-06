"""
PDF 文档解析器 — 将 PDF 转为脱敏后的 JSON 文档。

用法示例：
    python3 tools/pdf_parser.py \\
        --file document.pdf \\
        --context coworker \\
        --slug my-twin

依赖：pymupdf4llm（pip3 install pymupdf4llm）
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path

try:
    import pymupdf4llm
except ImportError:
    print("错误：请安装 pymupdf4llm：pip3 install pymupdf4llm", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.pii_scrubber import scrub
from tools.ingestion_output import validate_context_label, write_ingestion_json, add_common_args


# ─────────────────────────────────────────────────────────────────────────────
# 解析函数
# ─────────────────────────────────────────────────────────────────────────────

def parse_pdf(
    file_path: Path,
    use_llm_fallback: bool = False,
) -> tuple[list[dict], dict[str, int]]:
    """将 PDF 文件转为脱敏后的文本块列表。

    使用 pymupdf4llm 提取 PDF 内容为 Markdown 格式文本，
    按段落切分后对每块应用 PII 脱敏。

    对密码保护或损坏的 PDF 进行优雅降级，返回空列表。

    Args:
        file_path: PDF 文件路径。
        use_llm_fallback: 是否启用 LLM 脱敏回退。

    Returns:
        (chunks, combined_stats)
        chunks: 脱敏后的文本块列表。
        combined_stats: 各 PII 占位符的累计替换计数。
    """
    # T-03-02: 对 PDF 解析失败进行优雅处理
    try:
        md_text = pymupdf4llm.to_markdown(str(file_path))
    except Exception as e:
        print(
            f"警告：PDF 解析失败 ({e})，文件可能受密码保护",
            file=sys.stderr,
        )
        return [], {}

    if not md_text or not md_text.strip():
        return [], {}

    # 按段落切分（双换行分隔）
    raw_chunks = [c.strip() for c in md_text.split("\n\n") if c.strip()]

    chunks: list[dict] = []
    combined_stats: dict[str, int] = {}

    for i, raw_chunk in enumerate(raw_chunks):
        # T-03-03: scrub() 在解析函数内调用，不可被 CLI 绕过
        scrubbed_text, chunk_stats = scrub(raw_chunk, use_llm_fallback=use_llm_fallback)

        for key, count in chunk_stats.items():
            combined_stats[key] = combined_stats.get(key, 0) + count

        chunk = {
            "id": i,
            "text": scrubbed_text,
            "metadata": {
                "page_hint": i,
                "source_format": "pdf",
            },
        }
        chunks.append(chunk)

    return chunks, combined_stats


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 主入口：解析参数、调用 PDF 解析器、写入 JSON。"""
    parser = argparse.ArgumentParser(description="PDF 文档解析器")
    parser.add_argument(
        "--file",
        required=True,
        type=str,
        help="PDF 文件路径",
    )
    add_common_args(parser)

    args = parser.parse_args()

    # 文件存在性校验（路径规范化，防止路径穿越）
    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"错误：文件不存在：{file_path}", file=sys.stderr)
        sys.exit(1)

    context = validate_context_label(args.context)

    chunks, combined_stats = parse_pdf(
        file_path, use_llm_fallback=args.use_llm_fallback
    )

    if not chunks:
        print(
            "警告：未能从 PDF 中提取任何文本（可能为图片型 PDF 或空文件）",
            file=sys.stderr,
        )
        # 非致命错误：图片型 PDF 是正常情况，退出码 0
        sys.exit(0)

    write_ingestion_json(
        chunks=chunks,
        source_type="pdf",
        context_label=context,
        twin_slug=args.slug,
        source_file=str(file_path),
        scrub_stats=combined_stats,
        base_dir=Path(args.base_dir),
    )


if __name__ == "__main__":
    main()
