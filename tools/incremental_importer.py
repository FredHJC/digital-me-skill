#!/usr/bin/env python3
"""
增量导入器 — 将新数据批次导入已有数字分身的单个关系上下文。

仅更新目标上下文的提取制品和 facet，不修改 core.md 或其他上下文文件。
导入前自动备份，导入后运行隐私守卫，最后更新 meta.json。

用法示例：
    python3 tools/incremental_importer.py \
        --slug zhangsan \
        --context partner \
        --input-json ./new_batch.json \
        --base-dir ./twins
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─────────────────────────────────────────────────────────────────────────────
# 公开 API
# ─────────────────────────────────────────────────────────────────────────────

def incremental_import(
    slug: str,
    context: str,
    input_json: Path,
    base_dir: Path,
    name: Optional[str] = None,
) -> list[Path]:
    """对已有数字分身执行单上下文增量导入。

    执行顺序（防回归设计）：
    1. 预检：context 标签规范化、twin 目录和 core.md 存在性验证
    2. 备份当前版本
    3. 将输入 JSON 复制到 knowledge/{context}/ 目录
    4. 重新提取目标上下文（仅覆盖 extractions/{context}.json）
    5. 重新合成目标 facet（仅覆盖 facets/{context}.md；core.md 不动）
    6. 重新生成所有 SKILL*.md（内含隐私守卫）
    7. 更新 meta.json（最后一步，仅在所有 SKILL 文件成功后执行）

    Args:
        slug: 数字分身的唯一标识符。
        context: 目标关系上下文标签（如 "partner"、"coworker"）。
        input_json: 预脱敏 JSON 文件路径（知识批次文件）。
        base_dir: twins 根目录路径。
        name: 数字分身姓名（不提供则从 meta.json 读取）。

    Returns:
        所有重新生成的 SKILL 文件路径列表。
    """
    # ── 步骤 1：预检 ──────────────────────────────────────────────────────────

    # 规范化 context 标签（空字符串会触发 sys.exit(1)）
    from tools.ingestion_output import validate_context_label
    context = validate_context_label(context)

    # 验证 twin 目录存在
    twin_dir = Path(base_dir) / slug
    if not twin_dir.exists():
        print(f"错误：数字分身目录不存在：{twin_dir}", file=sys.stderr)
        sys.exit(1)

    # 验证 core.md 存在（增量导入必须在初始合成后执行）
    core_path = twin_dir / "core.md"
    if not core_path.exists():
        print(
            f"错误：core.md 不存在，请先完成初始合成：{core_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 验证 meta.json 存在（必须先运行 /digital-twin create）
    meta_path = twin_dir / "meta.json"
    if not meta_path.exists():
        print(
            f"错误：meta.json 不存在，请先运行 /digital-twin create 创建数字分身：{meta_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 验证输入 JSON 文件存在
    input_json = Path(input_json)
    if not input_json.exists():
        print(f"错误：输入文件不存在：{input_json}", file=sys.stderr)
        sys.exit(1)

    # 验证输入 JSON 可解析
    try:
        json.loads(input_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"错误：输入文件不是有效 JSON：{exc}", file=sys.stderr)
        sys.exit(1)

    # ── 步骤 2：备份当前版本 ───────────────────────────────────────────────────

    from tools.version_manager import backup
    version_name = f"pre-incremental-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    backup(twin_dir, version_name)

    # ── 步骤 3：将输入文件复制到 knowledge/{context}/ ─────────────────────────

    knowledge_dir = twin_dir / "knowledge" / context
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest_filename = f"incremental_{timestamp}_{input_json.name}"
    shutil.copy2(input_json, knowledge_dir / dest_filename)

    # ── 步骤 4：重新提取目标上下文 ────────────────────────────────────────────

    from tools.behavioral_extractor import extract_context
    extract_context(slug, context, base_dir)

    # ── 步骤 5：重新合成目标 facet ────────────────────────────────────────────

    from tools.twin_synthesizer import synthesize_facet
    synthesize_facet(slug, context, base_dir)

    # ── 步骤 6：重新生成所有 SKILL*.md（隐私守卫在 generate_skill_files 内触发）─

    from tools.twin_skill_writer import generate_skill_files
    meta_path = twin_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    twin_name = name or meta.get("name", slug)
    generated = generate_skill_files(slug, twin_name, base_dir)

    # ── 步骤 7：更新 meta.json（最后执行，确保所有 SKILL 文件已成功写入）────────

    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    meta["last_incremental_context"] = context
    if "knowledge_sources" in meta and isinstance(meta["knowledge_sources"], list):
        meta["knowledge_sources"].append({
            "context": context,
            "imported_at": meta["updated_at"],
            "source": str(input_json.name),
        })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"增量导入完成：{slug}/{context}")
    return generated


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """增量导入器 CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="增量导入新数据批次到已有数字分身的指定关系上下文"
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="数字分身标识符",
    )
    parser.add_argument(
        "--context",
        required=True,
        help="目标关系上下文标签（如 coworker/partner/family/friend/自定义）",
    )
    parser.add_argument(
        "--input-json",
        required=True,
        help="预脱敏的知识批次 JSON 文件路径",
    )
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 根目录（默认：./twins）",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="数字分身姓名（不提供则从 meta.json 读取）",
    )

    args = parser.parse_args()
    incremental_import(
        args.slug,
        args.context,
        Path(args.input_json),
        Path(args.base_dir),
        args.name,
    )


if __name__ == "__main__":
    main()
