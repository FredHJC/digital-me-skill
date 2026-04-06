"""
数字分身 SKILL.md 生成器测试 — 覆盖注入防护、frontmatter 格式、内联嵌入、双语前言、反馈日志等。

测试类：
- TestInjectionShield: 注入防护内容验证
- TestSkillMdFormat: YAML frontmatter 格式验证
- TestInlineEmbed: 内联内容嵌入验证
- TestBilingualPreamble: 双语前言验证
- TestRoleFiles: 角色文件生成验证
- TestPrivacyGate: PII 隐私守卫验证
- TestFeedbackLog: 反馈日志写入验证
- TestFeedbackLogSchema: 反馈日志 schema 验证
- TestCLI: 命令行接口验证
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.twin_skill_writer import generate_skill_files, append_feedback


# ─────────────────────────────────────────────────────────────────────────────
# 辅助：创建测试用 twin 目录
# ─────────────────────────────────────────────────────────────────────────────

def _setup_twin_dir(twin_dir: Path) -> None:
    """创建标准测试 twin 目录，含 core.md、meta.json 和两个 facet 文件。"""
    # core.md — 安全的人物设定文本（无 PII）
    core_text = """# test-twin — Core Identity

## Identity

偏好逻辑驱动的沟通方式，在不同场合保持一致的工作态度。对问题有系统性思考习惯。

## Tone & Style

正式程度适中，偶尔使用幽默缓解紧张气氛。表达直接，节奏稳定。

## Vocabulary

常用词汇包括专业术语，句式简洁。

## Knowledge Boundaries

擅长产品管理和敏捷开发领域。

## Behavioral Limits

决策依赖数据支撑，冲突时倾向于回避对抗。
"""
    twin_dir.mkdir(parents=True, exist_ok=True)
    (twin_dir / "core.md").write_text(core_text, encoding="utf-8")

    # meta.json
    meta = {
        "name": "Test User",
        "slug": "test-twin",
        "context_labels": ["coworker", "partner"],
        "version": "v1",
        "created_at": "2026-04-05T00:00:00+00:00",
        "updated_at": "2026-04-05T00:00:00+00:00",
        "knowledge_sources": [],
    }
    (twin_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # facets/
    facets_dir = twin_dir / "facets"
    facets_dir.mkdir(parents=True, exist_ok=True)

    coworker_text = """# test-twin — coworker Facet

> Inherits from core.md — only context-specific adaptations below.

## Tone & Style

在工作环境中正式程度略高，更注重清晰的表达。

## Vocabulary

常用工作场景术语，如迭代、复盘、对齐。
"""
    (facets_dir / "coworker.md").write_text(coworker_text, encoding="utf-8")

    partner_text = """# test-twin — partner Facet

> Inherits from core.md — only context-specific adaptations below.

## Tone & Style

在亲密关系中更加轻松随意，偶尔使用表情和缩写。

## Vocabulary

更多日常词汇，减少工作术语。
"""
    (facets_dir / "partner.md").write_text(partner_text, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# TestInjectionShield — 注入防护内容验证
# ─────────────────────────────────────────────────────────────────────────────

class TestInjectionShield:
    """验证生成的 SKILL.md 包含正确的注入防护内容。"""

    def test_behavioral_rules_section_present(self, twin_dir: Path) -> None:
        """生成的 SKILL.md 包含 '行为守则 / Behavioral Rules' 节头。"""
        _setup_twin_dir(twin_dir)
        generated = generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        assert "Behavioral Rules" in content

    def test_no_compliance_signals(self, twin_dir: Path) -> None:
        """生成的 SKILL.md 不包含合规信号短语（'as an AI' 等），且若提及则仅在禁止语境中。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        # 'as an AI' 绝对不应出现
        assert "as an AI" not in content
        # 若提及 'I cannot' 或 'I am not allowed'，必须是在 'Do NOT' 禁止语境中
        if "I cannot" in content:
            assert "Do NOT" in content, "提及 'I cannot' 时必须有 'Do NOT' 禁止语境"
        if "I am not allowed" in content:
            assert "Do NOT" in content, "提及 'I am not allowed' 时必须有 'Do NOT' 禁止语境"

    def test_shield_before_core_identity(self, twin_dir: Path) -> None:
        """防护节出现在 'Core Identity' 节之前。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        shield_pos = content.find("Behavioral Rules")
        core_pos = content.find("Core Identity")
        assert shield_pos != -1, "未找到 Behavioral Rules 节"
        assert core_pos != -1, "未找到 Core Identity 节"
        assert shield_pos < core_pos, "防护节应在 Core Identity 之前"


# ─────────────────────────────────────────────────────────────────────────────
# TestSkillMdFormat — YAML frontmatter 格式验证
# ─────────────────────────────────────────────────────────────────────────────

class TestSkillMdFormat:
    """验证生成的 SKILL.md 包含有效的 AgentSkills frontmatter。"""

    def test_default_skill_md_frontmatter(self, twin_dir: Path) -> None:
        """默认 SKILL.md frontmatter 包含所有 6 个必填字段。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        assert "name:" in content
        assert "description:" in content
        assert "argument-hint:" in content
        assert "version:" in content
        assert "user-invocable:" in content
        assert "allowed-tools:" in content

    def test_default_skill_name_field(self, twin_dir: Path) -> None:
        """默认 SKILL.md frontmatter 的 name 字段等于 '{slug}'。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        assert "name: test-twin" in content

    def test_role_skill_name_field(self, twin_dir: Path) -> None:
        """角色 SKILL-{context}.md frontmatter 的 name 字段等于 '{slug}-as-{context}'。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        coworker_path = twin_dir / "SKILL-coworker.md"
        content = coworker_path.read_text(encoding="utf-8")
        assert "name: test-twin-as-coworker" in content


# ─────────────────────────────────────────────────────────────────────────────
# TestInlineEmbed — 内联内容嵌入验证
# ─────────────────────────────────────────────────────────────────────────────

class TestInlineEmbed:
    """验证 core.md 内容被内联嵌入到生成的 SKILL.md 中。"""

    def test_core_content_embedded(self, twin_dir: Path) -> None:
        """生成的 SKILL.md 包含 core.md 文本内容。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        core_content = (twin_dir / "core.md").read_text(encoding="utf-8")
        # 检查 core.md 中的关键文本片段存在于 SKILL.md 中
        assert "偏好逻辑驱动的沟通方式" in content

    def test_no_file_path_references(self, twin_dir: Path) -> None:
        """生成的 SKILL.md 不包含文件路径引用（如 'twins/'、'core.md'）。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        # 不应包含工具调用模式中的文件路径引用
        assert "twins/" not in content
        # core.md 不应作为文件引用出现（只允许 Run Rules 中的 feedback 命令路径）
        # 检查没有 Read tool 引用
        assert "Read tool" not in content


# ─────────────────────────────────────────────────────────────────────────────
# TestBilingualPreamble — 双语前言验证
# ─────────────────────────────────────────────────────────────────────────────

class TestBilingualPreamble:
    """验证生成的 SKILL.md 包含双语前言。"""

    def test_bilingual_preamble_present(self, twin_dir: Path) -> None:
        """生成的 SKILL.md 包含英文和中文双语前言文本。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        skill_md_path = twin_dir / "SKILL.md"
        content = skill_md_path.read_text(encoding="utf-8")
        # 英文前言
        assert "Language" in content
        assert "This skill supports both English and Chinese" in content
        # 中文前言
        assert "本 Skill 支持中英文" in content


# ─────────────────────────────────────────────────────────────────────────────
# TestRoleFiles — 角色文件生成验证
# ─────────────────────────────────────────────────────────────────────────────

class TestRoleFiles:
    """验证角色 SKILL 文件的生成数量和内容。"""

    def test_file_count_with_two_facets(self, twin_dir: Path) -> None:
        """包含 2 个 facet 的 twin -> 生成恰好 3 个文件（SKILL.md + 2 个 SKILL-{context}.md）。"""
        _setup_twin_dir(twin_dir)
        generated = generate_skill_files("test-twin", "Test User", twin_dir.parent)
        assert len(generated) == 3

    def test_role_file_embeds_core_and_facet(self, twin_dir: Path) -> None:
        """每个 SKILL-{context}.md 同时嵌入 core.md 和对应 facet 的内容。"""
        _setup_twin_dir(twin_dir)
        generate_skill_files("test-twin", "Test User", twin_dir.parent)
        coworker_path = twin_dir / "SKILL-coworker.md"
        content = coworker_path.read_text(encoding="utf-8")
        # 包含 core 内容
        assert "偏好逻辑驱动的沟通方式" in content
        # 包含 coworker facet 内容
        assert "工作场景术语" in content


# ─────────────────────────────────────────────────────────────────────────────
# TestPrivacyGate — PII 隐私守卫验证
# ─────────────────────────────────────────────────────────────────────────────

class TestPrivacyGate:
    """验证含 PII 的 core.md 被阻止写入 SKILL.md。"""

    def test_pii_in_core_causes_exit_1(self, twin_dir: Path) -> None:
        """core.md 包含手机号 13912345678 -> generate_skill_files 以 SystemExit(1) 退出。"""
        _setup_twin_dir(twin_dir)
        # 注入 PII：手机号
        pii_core = """# test-twin — Core Identity

## Identity

联系方式是 13912345678，请随时联系。偏好逻辑驱动的沟通方式。
"""
        (twin_dir / "core.md").write_text(pii_core, encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            generate_skill_files("test-twin", "Test User", twin_dir.parent)

        assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestFeedbackLog — 反馈日志写入验证
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackLog:
    """验证 append_feedback() 正确写入 feedback.log。"""

    def test_single_feedback_creates_log(self, twin_dir: Path) -> None:
        """调用一次 append_feedback -> feedback.log 存在且有一行 JSONL。"""
        _setup_twin_dir(twin_dir)
        append_feedback("test-twin", twin_dir.parent, "coworker", "这不像你说话的方式")
        feedback_path = twin_dir / "feedback.log"
        assert feedback_path.exists()
        lines = [l for l in feedback_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1

    def test_double_append_produces_two_lines(self, twin_dir: Path) -> None:
        """调用两次 append_feedback -> feedback.log 有 2 行。"""
        _setup_twin_dir(twin_dir)
        append_feedback("test-twin", twin_dir.parent, "coworker", "第一条反馈")
        append_feedback("test-twin", twin_dir.parent, "partner", "第二条反馈")
        feedback_path = twin_dir / "feedback.log"
        lines = [l for l in feedback_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2


# ─────────────────────────────────────────────────────────────────────────────
# TestFeedbackLogSchema — 反馈日志 schema 验证
# ─────────────────────────────────────────────────────────────────────────────

class TestFeedbackLogSchema:
    """验证 feedback.log 中每条 JSONL 记录包含所需字段。"""

    def test_feedback_entry_has_required_fields(self, twin_dir: Path) -> None:
        """每条 JSONL 记录包含 'ts'、'role'、'visitor_msg' 字段。"""
        _setup_twin_dir(twin_dir)
        append_feedback("test-twin", twin_dir.parent, "coworker", "测试反馈消息")
        feedback_path = twin_dir / "feedback.log"
        line = feedback_path.read_text(encoding="utf-8").strip()
        entry = json.loads(line)
        assert "ts" in entry
        assert "role" in entry
        assert "visitor_msg" in entry
        assert entry["role"] == "coworker"
        assert entry["visitor_msg"] == "测试反馈消息"

    def test_feedback_entry_has_twin_response_field(self, twin_dir: Path) -> None:
        """append_feedback() 传入 twin_response 时，JSONL 记录包含该字段。"""
        _setup_twin_dir(twin_dir)
        append_feedback(
            "test-twin", twin_dir.parent, "coworker", "这不像你",
            twin_response="我觉得你应该加班",
        )
        feedback_path = twin_dir / "feedback.log"
        entry = json.loads(feedback_path.read_text(encoding="utf-8").strip())
        assert entry["twin_response"] == "我觉得你应该加班"

    def test_feedback_entry_has_visitor_query_field(self, twin_dir: Path) -> None:
        """append_feedback() 传入 visitor_query 时，JSONL 记录包含该字段。"""
        _setup_twin_dir(twin_dir)
        append_feedback(
            "test-twin", twin_dir.parent, "coworker", "你不会这么说",
            visitor_query="周末要不要加班？",
        )
        feedback_path = twin_dir / "feedback.log"
        entry = json.loads(feedback_path.read_text(encoding="utf-8").strip())
        assert entry["visitor_query"] == "周末要不要加班？"

    def test_feedback_backward_compat(self, twin_dir: Path) -> None:
        """不传 twin_response/visitor_query 时，默认值为空字符串。"""
        _setup_twin_dir(twin_dir)
        append_feedback("test-twin", twin_dir.parent, "coworker", "旧调用方式")
        feedback_path = twin_dir / "feedback.log"
        entry = json.loads(feedback_path.read_text(encoding="utf-8").strip())
        assert entry["twin_response"] == ""
        assert entry["visitor_query"] == ""

    def test_run_rule_contains_twin_response_flag(self, twin_dir: Path) -> None:
        """生成的 SKILL.md 的 Run Rule 包含 --twin-response 和 --visitor-query 标志。"""
        _setup_twin_dir(twin_dir)
        generated = generate_skill_files("test-twin", "测试", twin_dir.parent)
        skill_path = generated[0]
        content = skill_path.read_text(encoding="utf-8")
        assert "--twin-response" in content
        assert "--visitor-query" in content


# ─────────────────────────────────────────────────────────────────────────────
# TestCLI — 命令行接口验证
# ─────────────────────────────────────────────────────────────────────────────

class TestCLI:
    """验证 twin_skill_writer.py CLI 入口。"""

    def test_cli_generates_skill_md(self, twin_dir: Path) -> None:
        """运行 CLI --slug test-twin --base-dir {tmp} -> 退出 0 并生成 SKILL.md。"""
        _setup_twin_dir(twin_dir)
        project_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "tools/twin_skill_writer.py",
                "--slug", "test-twin",
                "--base-dir", str(twin_dir.parent),
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0, f"CLI 失败: {result.stderr}"
        skill_md_path = twin_dir / "SKILL.md"
        assert skill_md_path.exists(), "SKILL.md 未被生成"
