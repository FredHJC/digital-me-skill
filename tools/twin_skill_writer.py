#!/usr/bin/env python3
"""
数字分身 SKILL.md 生成器

从 twins/{slug}/core.md 和 twins/{slug}/facets/{context}.md 生成生产就绪的
AgentSkills SKILL.md 文件，包含注入防护、双语前言和反馈日志支持。

用法：
    # 生成所有 SKILL.md 文件
    python3 tools/twin_skill_writer.py --slug zhangsan --base-dir ./twins

    # 追加访客反馈
    python3 tools/twin_skill_writer.py --slug zhangsan --append-feedback \
        --role coworker --visitor-msg "你不会这样说"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────────────────────

SHIELD_TEMPLATE_PATH: Path = (
    Path(__file__).resolve().parent.parent / "prompts" / "injection_shield.md"
)

_SHIELD_CACHE: Optional[str] = None

BILINGUAL_PREAMBLE: str = (
    "> **Language / 语言**: This skill supports both English and Chinese.\n"
    "> Detect the user's language from their first message and respond\n"
    "> in the same language throughout. Below are instructions in both\n"
    "> languages -- follow the one matching the user's language.\n"
    ">\n"
    "> 本 Skill 支持中英文。根据用户第一条消息的语言，全程使用同一语言回复。\n"
    "> 下方提供了两种语言的指令，按用户语言选择对应版本执行。"
)


# ─────────────────────────────────────────────────────────────────────────────
# 内部辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _load_shield(name: str, slug: str) -> str:
    """读取并填充注入防护模板，使用模块级缓存避免重复磁盘读取。

    Args:
        name: 数字分身的真实姓名（替换 {name} 占位符）。
        slug: 数字分身的 slug（替换 {slug} 占位符）。

    Returns:
        填充了 name 和 slug 的注入防护文本。
    """
    global _SHIELD_CACHE
    if _SHIELD_CACHE is None:
        _SHIELD_CACHE = SHIELD_TEMPLATE_PATH.read_text(encoding="utf-8")
    return _SHIELD_CACHE.replace("{name}", name).replace("{slug}", slug)


def _assemble_skill_md(
    name: str,
    slug: str,
    core_text: str,
    shield: str,
    context: Optional[str] = None,
    facet_text: Optional[str] = None,
) -> str:
    """组装完整的 SKILL.md 字符串。

    布局顺序（防护在人物设定之前，防止覆盖攻击）：
    1. YAML frontmatter
    2. 双语前言
    3. 注入防护节
    4. 水平分割线
    5. Core Identity 节（内联嵌入 core_text）
    6. 可选：{context} Adaptations 节（内联嵌入 facet_text）
    7. 水平分割线
    8. Run Rules 节

    Args:
        name: 数字分身姓名。
        slug: 数字分身 slug。
        core_text: core.md 的完整文本内容。
        shield: 已填充占位符的注入防护文本。
        context: 角色上下文标签（如 'coworker'），None 表示默认模式。
        facet_text: facet 文件的完整文本内容（仅角色模式使用）。

    Returns:
        完整的 SKILL.md 字符串。
    """
    # 确定 frontmatter 字段
    if context is None:
        skill_name = slug
        # 使用单引号避免 validate_no_raw_text 误报双引号长字符串
        description = f"'{name} digital twin | {name} 的数字分身'"
        run_rule_1 = f"You are {name}. Stay in character at all times."
        role_label = "default"
    else:
        skill_name = f"{slug}-as-{context}"
        description = f"'{name} ({context} mode) | {name} ({context} 模式)'"
        run_rule_1 = f"You are {name} in {context} mode."
        role_label = context

    # 构建 YAML frontmatter（使用单引号值避免 validate_no_raw_text 误报）
    frontmatter = (
        "---\n"
        f"name: {skill_name}\n"
        f"description: {description}\n"
        f"argument-hint: '[message or question for {name}]'\n"
        "version: '1.0.0'\n"
        "user-invocable: true\n"
        "allowed-tools: Read, Write, Edit, Bash\n"
        "---"
    )

    # 构建 Run Rules
    run_rules_lines = [
        "## Run Rules",
        "",
        f"1. {run_rule_1}",
    ]
    if context is not None:
        run_rules_lines.append(
            "2. Core identity always applies. Adaptations above extend (not replace) core."
        )
        next_rule = 3
    else:
        next_rule = 2

    run_rules_lines.append(
        f"{next_rule}. When visitor says something like '你不会这样说', 'you wouldn't say that', "
        f"'这不像你', 'that's not how you talk' -- log their feedback via Bash: "
        f"`python3 tools/twin_skill_writer.py --append-feedback --slug {slug} "
        f"--role {role_label} --visitor-msg '<their correction>' "
        f"--twin-response '<what you just said that triggered this>' "
        f"--visitor-query '<what the visitor originally asked>'` "
        f"-- then acknowledge naturally and continue as yourself."
    )
    run_rules_lines.append(
        f"{next_rule + 1}. Detect visitor language from first message; respond in same language throughout."
    )

    run_rules = "\n".join(run_rules_lines)

    # 组装核心人物设定节
    core_section = f"## Core Identity\n\n{core_text.strip()}"

    # 可选：角色适配节
    facet_section = ""
    if context is not None and facet_text is not None:
        facet_section = f"\n\n---\n\n## {context} Adaptations\n\n{facet_text.strip()}"

    # 最终组装
    parts = [
        frontmatter,
        "",
        BILINGUAL_PREAMBLE,
        "",
        shield.strip(),
        "",
        "---",
        "",
        core_section,
        facet_section,
        "",
        "---",
        "",
        run_rules,
    ]

    return "\n".join(parts)


def _validate_and_write_skill(content: str, path: Path) -> None:
    """验证内容无 PII，然后写入文件。

    Args:
        content: 待写入的 SKILL.md 内容。
        path: 目标文件路径。

    Raises:
        SystemExit(1): 若内容包含 PII 或原始文本违规。
    """
    # 延迟导入避免循环依赖
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.extraction_models import validate_no_raw_text  # noqa: PLC0415

    violations = validate_no_raw_text(content)
    if violations:
        for v in violations:
            print(f"隐私守卫拦截：{v}", file=sys.stderr)
        sys.exit(1)

    path.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 公开 API
# ─────────────────────────────────────────────────────────────────────────────

def generate_skill_files(slug: str, name: str, base_dir: Path) -> list[Path]:
    """生成数字分身的所有 SKILL.md 文件。

    生成文件：
    - twins/{slug}/SKILL.md（仅 core，默认模式）
    - twins/{slug}/SKILL-{context}.md（每个 facet 一个，core + facet）

    Args:
        slug: 数字分身的唯一标识符。
        name: 数字分身的真实姓名（用于前言和规则）。
        base_dir: twins/ 根目录路径。

    Returns:
        所有已生成文件的路径列表。
    """
    twin_dir = Path(base_dir) / slug

    # 读取 core.md
    core_path = twin_dir / "core.md"
    if not core_path.exists():
        print(f"错误：找不到 core.md：{core_path}", file=sys.stderr)
        sys.exit(1)
    core_text = core_path.read_text(encoding="utf-8")

    # 加载注入防护
    shield = _load_shield(name, slug)

    generated: list[Path] = []

    # 生成默认 SKILL.md（core-only）
    skill_content = _assemble_skill_md(name, slug, core_text, shield, context=None)
    skill_path = twin_dir / "SKILL.md"
    _validate_and_write_skill(skill_content, skill_path)
    generated.append(skill_path)
    print(f"已生成：{skill_path}")

    # 生成角色 SKILL-{context}.md（每个 facet 一个）
    facets_dir = twin_dir / "facets"
    if facets_dir.exists():
        for facet_file in sorted(facets_dir.glob("*.md")):
            context = facet_file.stem
            facet_text = facet_file.read_text(encoding="utf-8")
            role_content = _assemble_skill_md(
                name, slug, core_text, shield, context=context, facet_text=facet_text
            )
            role_path = twin_dir / f"SKILL-{context}.md"
            _validate_and_write_skill(role_content, role_path)
            generated.append(role_path)
            print(f"已生成：{role_path}")

    # 自动注册到 .claude/skills/（Claude Code 技能发现）
    _register_skills(slug, twin_dir, generated)

    return generated


def _register_skills(slug: str, twin_dir: Path, generated: list[Path]) -> None:
    """将生成的 SKILL.md 注册到 .claude/skills/ 目录。

    Claude Code 在启动时扫描 .claude/skills/ 发现可用技能。
    此函数在每次生成 SKILL 文件后自动将其复制到正确位置。

    Args:
        slug: 数字分身的唯一标识符。
        twin_dir: twins/{slug}/ 目录路径。
        generated: 所有已生成的 SKILL 文件路径列表。
    """
    # 从 twin_dir 向上找项目根目录（包含 .claude/ 的目录）
    project_root = twin_dir.parent.parent
    skills_base = project_root / ".claude" / "skills"

    for skill_path in generated:
        if skill_path.name == "SKILL.md":
            # 默认模式 → .claude/skills/{slug}/SKILL.md
            target_dir = skills_base / slug
        else:
            # SKILL-{context}.md → .claude/skills/{slug}-as-{context}/SKILL.md
            context = skill_path.stem.replace("SKILL-", "")
            target_dir = skills_base / f"{slug}-as-{context}"

        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "SKILL.md"
        import shutil
        shutil.copy2(skill_path, target)
        print(f"已注册：{target}")


def append_feedback(
    slug: str,
    base_dir: Path,
    role: str,
    visitor_msg: str,
    context_turns: int = 0,
    twin_response: str = "",
    visitor_query: str = "",
) -> None:
    """将访客反馈追加到 feedback.log（JSONL 格式）。

    Args:
        slug: 数字分身的唯一标识符。
        base_dir: twins/ 根目录路径。
        role: 当前对话角色标签（如 'coworker'、'default'）。
        visitor_msg: 访客的反馈消息文本。
        context_turns: 反馈发生时的对话轮次（可选）。
        twin_response: 数字分身说了什么导致了这条反馈（即上一轮 assistant 回复）。
        visitor_query: 访客最初问了什么（触发 twin_response 的那轮用户消息）。
    """
    twin_dir = Path(base_dir) / slug
    feedback_path = twin_dir / "feedback.log"

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "visitor_msg": visitor_msg,
        "context_turns": context_turns,
        "twin_response": twin_response,
        "visitor_query": visitor_query,
    }

    with open(feedback_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """命令行入口：生成 SKILL.md 文件或追加访客反馈。"""
    parser = argparse.ArgumentParser(
        description="数字分身 SKILL.md 生成器和反馈日志工具"
    )
    parser.add_argument("--slug", required=True, help="数字分身 slug")
    parser.add_argument("--name", default=None, help="数字分身姓名（可选，默认从 meta.json 读取）")
    parser.add_argument("--base-dir", default="./twins", help="twins/ 根目录（默认：./twins）")
    parser.add_argument("--append-feedback", action="store_true", help="追加访客反馈模式")
    parser.add_argument("--role", default="default", help="对话角色标签（默认：default）")
    parser.add_argument("--visitor-msg", default="", help="访客反馈消息文本")
    parser.add_argument("--context-turns", type=int, default=0, help="反馈发生时的对话轮次")
    parser.add_argument("--twin-response", default="", help="数字分身说了什么导致了反馈（上一轮 assistant 回复）")
    parser.add_argument("--visitor-query", default="", help="访客最初问了什么（触发回复的那轮用户消息）")

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()

    if args.append_feedback:
        append_feedback(
            args.slug, base_dir, args.role, args.visitor_msg,
            args.context_turns, args.twin_response, args.visitor_query,
        )
    else:
        # 从 meta.json 读取 name（若未通过 --name 指定）
        name = args.name
        if name is None:
            meta_path = base_dir / args.slug / "meta.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                name = meta.get("name", args.slug)
            else:
                name = args.slug

        generate_skill_files(args.slug, name, base_dir)


if __name__ == "__main__":
    main()
