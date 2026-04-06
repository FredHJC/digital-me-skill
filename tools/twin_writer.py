#!/usr/bin/env python3
"""
Twin 目录管理器 — 创建和管理数字分身目录结构。

负责创建 twins/{slug}/ 目录结构，写入 meta.json，
并提供列出所有数字分身的功能。

用法：
    python3 twin_writer.py --action create --slug zhangsan \
        --name "张三" --context-labels coworker,partner,family,friend

    python3 twin_writer.py --action list --base-dir ./twins
"""

from __future__ import annotations

import json
import re
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Slug 生成
# ─────────────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """
    将姓名转为 slug。
    优先尝试 pypinyin（如已安装），否则 fallback 到简单处理。
    """
    # 尝试用 pypinyin 转拼音
    try:
        from pypinyin import lazy_pinyin
        parts = lazy_pinyin(name)
        slug = "_".join(parts)
    except ImportError:
        # fallback：保留 ASCII 字母数字，中文直接去掉
        import unicodedata
        result = []
        for char in name.lower():
            if char.isascii() and (char.isalnum() or char in ("-", "_")):
                result.append(char)
            elif char == " ":
                result.append("_")
            # 中文字符跳过（无 pypinyin 时无法转换）
        slug = "".join(result)

    # 清理：去掉连续下划线，首尾下划线
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug if slug else "twin"


# ─────────────────────────────────────────────────────────────────────────────
# 目录创建
# ─────────────────────────────────────────────────────────────────────────────

def create_twin(
    slug: str,
    name: str,
    context_labels: list[str],
    base_dir: Path = Path("./twins"),
) -> Path:
    """创建数字分身目录结构。

    在 {base_dir}/{slug}/ 下创建以下结构：
        versions/           历史版本存档
        knowledge/          导入的知识文档（按关系标签分子目录）
        knowledge/{label}/  各关系标签的知识文档目录
        meta.json           数字分身元数据

    Args:
        slug: 数字分身的唯一标识符（URL 安全）。
        name: 数字分身的显示名称。
        context_labels: 关系标签列表，如 ["coworker", "partner"]。
        base_dir: twins 根目录，默认 ./twins。

    Returns:
        创建的数字分身目录路径。
    """
    twin_dir = Path(base_dir) / slug
    twin_dir.mkdir(parents=True, exist_ok=True)
    (twin_dir / "versions").mkdir(exist_ok=True)
    (twin_dir / "knowledge").mkdir(exist_ok=True)
    (twin_dir / "extractions").mkdir(exist_ok=True)
    (twin_dir / "facets").mkdir(exist_ok=True)

    # 为每个关系标签创建知识子目录
    for label in context_labels:
        (twin_dir / "knowledge" / label).mkdir(exist_ok=True)

    # 创建空 feedback.log（避免 /digital-twin:review 时文件不存在）
    feedback_path = twin_dir / "feedback.log"
    if not feedback_path.exists():
        feedback_path.touch()

    # 写入 meta.json
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "name": name,
        "slug": slug,
        "context_labels": context_labels,
        "version": "v1",
        "created_at": now,
        "updated_at": now,
        "knowledge_sources": [],
    }
    meta_path = twin_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已创建数字分身目录：{twin_dir}")
    return twin_dir


# ─────────────────────────────────────────────────────────────────────────────
# 列出数字分身
# ─────────────────────────────────────────────────────────────────────────────

def list_twins(base_dir: Path = Path("./twins")) -> list[dict]:
    """列出所有数字分身。

    扫描 {base_dir}/ 下的所有子目录，读取 meta.json 返回元数据列表。

    Args:
        base_dir: twins 根目录，默认 ./twins。

    Returns:
        数字分身元数据列表，按目录名排序。
    """
    twins = []
    base_dir = Path(base_dir)
    if not base_dir.exists():
        return twins
    for d in sorted(base_dir.iterdir()):
        meta_path = d / "meta.json"
        if d.is_dir() and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                twins.append(meta)
            except Exception:
                continue
    return twins


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 主入口：解析参数，执行创建或列出操作。"""
    parser = argparse.ArgumentParser(description="Twin 目录管理器")
    parser.add_argument(
        "--action",
        required=True,
        choices=["create", "list"],
        help="操作类型：create（创建）或 list（列出）",
    )
    parser.add_argument("--slug", help="数字分身 slug（用于目录名）")
    parser.add_argument("--name", help="数字分身显示名称")
    parser.add_argument(
        "--context-labels",
        help="关系标签，逗号分隔（例如：coworker,partner,family,friend）",
    )
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 基础目录（默认：./twins）",
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()

    if args.action == "list":
        twins = list_twins(base_dir)
        if not twins:
            print("暂无已创建的数字分身")
        else:
            print(f"已创建 {len(twins)} 个数字分身：\n")
            for t in twins:
                updated = t.get("updated_at", "")[:10] if t.get("updated_at") else "未知"
                labels = ", ".join(t.get("context_labels", []))
                print(f"  [{t.get('slug', '')}]  {t.get('name', '')} — {labels}")
                print(f"    版本: {t.get('version', 'v1')}  更新: {updated}")
                print()

    elif args.action == "create":
        if not args.slug and not args.name:
            print("错误：create 操作需要 --slug 或 --name", file=sys.stderr)
            sys.exit(1)

        name = args.name or args.slug or "数字分身"
        slug = args.slug or slugify(name)

        labels: list[str] = []
        if args.context_labels:
            labels = [l.strip() for l in args.context_labels.split(",") if l.strip()]

        twin_dir = create_twin(slug, name, labels, base_dir)
        print(f"✅ 数字分身已创建：{twin_dir}")


if __name__ == "__main__":
    main()
