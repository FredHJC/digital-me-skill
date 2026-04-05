"""
隐私审计工具 — 扫描 twins/{slug}/knowledge/ 中的所有 JSON 文件，
对每个 chunk 调用 LLM 脱敏，自动修复含个人叙述的内容，并写入审计报告。

用法：
    python3 tools/privacy_auditor.py --slug jiachen
    python3 tools/privacy_auditor.py --slug jiachen --base-dir ./twins

注意：
- 报告 (privacy_audit_report.json) 仅包含 chunk_id 和抽象标签类型，
  不保存任何原始文本（per D-05 防隐私泄露要求）
- 需要 ANTHROPIC_API_KEY 环境变量；若未设置，_llm_scrub 会优雅降级
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.pii_scrubber import _llm_scrub


# ─────────────────────────────────────────────────────────────────────────────
# 主逻辑
# ─────────────────────────────────────────────────────────────────────────────

def audit_twin(slug: str, base_dir: Path) -> Path:
    """扫描指定 twin 的所有 knowledge JSON 文件，修复含个人叙述的 chunk。

    对每个 chunk 调用 _llm_scrub()；若返回非空 abstractions，则：
    1. 将 chunk["text"] 替换为脱敏版本
    2. 重写 JSON 文件
    3. 在审计报告中记录 finding（仅保存 file、chunk_id、abstractions，无原始文本）

    审计报告写入：{base_dir}/{slug}/privacy_audit_report.json

    Args:
        slug: 数字分身的唯一标识符。
        base_dir: twins 根目录。

    Returns:
        写入的审计报告文件路径。
    """
    base_dir = Path(base_dir)
    knowledge_root = base_dir / slug / "knowledge"

    if not knowledge_root.exists():
        print(f"错误：知识库目录不存在：{knowledge_root}", file=sys.stderr)
        sys.exit(1)

    findings: list[dict] = []
    files_modified: int = 0

    # 遍历所有 JSON 文件（排序保证确定性输出）
    for json_file in sorted(knowledge_root.rglob("*.json")):
        try:
            doc = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"警告：无法读取 {json_file}：{exc}", file=sys.stderr)
            continue

        chunks = doc.get("chunks", [])
        if not chunks:
            continue

        file_modified = False

        for chunk in chunks:
            original_text = chunk.get("text", "")
            if not original_text:
                continue

            scrubbed_text, abstractions = _llm_scrub(original_text)

            if abstractions:
                # 修复 chunk（不保存原始文本 — per D-05 / T-02-02）
                chunk["text"] = scrubbed_text
                file_modified = True

                # 记录 finding：只含 file、chunk_id、abstractions（无 before/after）
                findings.append({
                    "file": str(json_file),
                    "chunk_id": chunk.get("id"),
                    "abstractions": abstractions,
                })

        if file_modified:
            # 原地重写文件（保留 ensure_ascii=False 以保留中文）
            json_file.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            files_modified += 1

    # 写入审计报告
    report = {
        "slug": slug,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": len(findings),
        "total_files_modified": files_modified,
        "findings": findings,
    }

    report_path = base_dir / slug / "privacy_audit_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"隐私审计完成：检测到 {len(findings)} 处需要修正，已自动修复"
    )

    return report_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI 主入口：解析参数，执行隐私审计。"""
    parser = argparse.ArgumentParser(
        description="隐私审计工具 — 扫描 twin knowledge 文件并自动修复个人叙述内容",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="数字分身的 slug 标识（twins 目录下的子目录名）",
    )
    parser.add_argument(
        "--base-dir",
        default="./twins",
        help="twins 根目录（默认：./twins）",
    )

    args = parser.parse_args()
    audit_twin(args.slug, Path(args.base_dir))


if __name__ == "__main__":
    main()
