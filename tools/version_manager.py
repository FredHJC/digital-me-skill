#!/usr/bin/env python3
"""
Twin 版本管理器

负责数字分身文件的版本存档和回滚。

用法：
    python version_manager.py --action list --slug zhangsan --base-dir ./twins
    python version_manager.py --action backup --slug zhangsan --version v1 --base-dir ./twins
    python version_manager.py --action rollback --slug zhangsan --version v1 --base-dir ./twins
"""

from __future__ import annotations

import json
import shutil
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

MAX_VERSIONS = 10  # 最多保留的版本数

# Phase 3: meta.json + core.md
TWIN_FILES: tuple[str, ...] = ("meta.json", "core.md")


def list_versions(twin_dir: Path) -> list:
    """列出所有历史版本"""
    versions_dir = twin_dir / "versions"
    if not versions_dir.exists():
        return []

    versions = []
    for v_dir in sorted(versions_dir.iterdir()):
        if not v_dir.is_dir():
            continue

        # 从目录名解析版本号
        version_name = v_dir.name

        # 获取存档时间（用目录修改时间近似）
        mtime = v_dir.stat().st_mtime
        archived_at = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

        # 统计文件
        files = [f.name for f in v_dir.iterdir() if f.is_file()]

        versions.append({
            "version": version_name,
            "archived_at": archived_at,
            "files": files,
            "path": str(v_dir),
        })

    return versions


def backup(twin_dir: Path, version_name: str) -> bool:
    """备份当前版本"""
    versions_dir = twin_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    target = versions_dir / version_name
    if target.exists():
        print(f"版本 {version_name} 已存在", file=sys.stderr)
        return False
    target.mkdir()
    for fname in TWIN_FILES:
        src = twin_dir / fname
        if src.exists():
            shutil.copy2(src, target / fname)
    # Also backup knowledge/ directory
    knowledge_src = twin_dir / "knowledge"
    if knowledge_src.exists():
        shutil.copytree(knowledge_src, target / "knowledge")
    # Also backup facets/ directory
    facets_src = twin_dir / "facets"
    if facets_src.exists():
        shutil.copytree(facets_src, target / "facets")
    # Backup all SKILL*.md files (Phase 4 extension)
    for skill_file in twin_dir.glob("SKILL*.md"):
        shutil.copy2(skill_file, target / skill_file.name)
    print(f"已备份到：{target}")
    return True


def rollback(twin_dir: Path, target_version: str) -> bool:
    """回滚到指定版本"""
    version_dir = twin_dir / "versions" / target_version
    if not version_dir.exists():
        print(f"版本 {target_version} 不存在", file=sys.stderr)
        return False
    for fname in TWIN_FILES:
        src = version_dir / fname
        if src.exists():
            shutil.copy2(src, twin_dir / fname)
    # Restore knowledge/ if backed up
    knowledge_backup = version_dir / "knowledge"
    if knowledge_backup.exists():
        knowledge_dest = twin_dir / "knowledge"
        if knowledge_dest.exists():
            shutil.rmtree(knowledge_dest)
        shutil.copytree(knowledge_backup, knowledge_dest)
    # Restore facets/ if backed up
    facets_backup = version_dir / "facets"
    if facets_backup.exists():
        facets_dest = twin_dir / "facets"
        if facets_dest.exists():
            shutil.rmtree(facets_dest)
        shutil.copytree(facets_backup, facets_dest)
    # Remove current SKILL*.md before restoring backed-up versions
    for stale_skill in twin_dir.glob("SKILL*.md"):
        stale_skill.unlink()
    # Restore backed-up SKILL*.md files
    for skill_file in version_dir.glob("SKILL*.md"):
        shutil.copy2(skill_file, twin_dir / skill_file.name)
    print(f"已回滚到版本：{target_version}")
    return True


def cleanup_old_versions(twin_dir: Path, max_versions: int = MAX_VERSIONS):
    """清理超出限制的旧版本"""
    versions_dir = twin_dir / "versions"
    if not versions_dir.exists():
        return

    # 按版本号排序，保留最新的 max_versions 个
    version_dirs = sorted(
        [d for d in versions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
    )

    to_delete = version_dirs[:-max_versions] if len(version_dirs) > max_versions else []

    for old_dir in to_delete:
        shutil.rmtree(old_dir)
        print(f"已清理旧版本：{old_dir.name}")


def main():
    parser = argparse.ArgumentParser(description="Twin 版本管理器")
    parser.add_argument("--action", required=True, choices=["list", "backup", "rollback", "cleanup"])
    parser.add_argument("--slug", required=True, help="数字分身 slug")
    parser.add_argument("--version", help="目标版本号（backup/rollback 时使用）")
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 根目录",
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()
    twin_dir = base_dir / args.slug

    if not twin_dir.exists():
        print(f"错误：找不到 Twin 目录 {twin_dir}", file=sys.stderr)
        sys.exit(1)

    if args.action == "list":
        versions = list_versions(twin_dir)
        if not versions:
            print(f"{args.slug} 暂无历史版本")
        else:
            print(f"{args.slug} 的历史版本：\n")
            for v in versions:
                print(f"  {v['version']}  存档时间: {v['archived_at']}  文件: {', '.join(v['files'])}")

    elif args.action == "backup":
        if not args.version:
            print("错误：backup 操作需要 --version", file=sys.stderr)
            sys.exit(1)
        success = backup(twin_dir, args.version)
        if not success:
            sys.exit(1)
        cleanup_old_versions(twin_dir)

    elif args.action == "rollback":
        if not args.version:
            print("错误：rollback 操作需要 --version", file=sys.stderr)
            sys.exit(1)
        success = rollback(twin_dir, args.version)
        if not success:
            sys.exit(1)

    elif args.action == "cleanup":
        cleanup_old_versions(twin_dir)
        print("清理完成")


if __name__ == "__main__":
    main()
