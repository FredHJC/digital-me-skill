<p align="center">
  <h1 align="center">Digital Twin Skill</h1>
  <p align="center">
    <strong>用你的聊天记录，蒸馏出一个会说话的 TA。</strong><br>
    <strong>Distill anyone's conversation style into an AI that talks like them.</strong>
  </p>
  <p align="center">
    <a href="#中文">中文</a> | <a href="#english">English</a>
  </p>
</p>

<p align="center">
  <em>"All data that exists is both reality and fantasy."</em><br>
  <em>所有存在的数据，既是现实，也是幻想。</em><br>
  —— Ghost in the Shell
</p>

---

<p align="center">
  你的另一半出差了，没法时刻回复你的消息；<br>
  你的好友也很忙，聊天记录停在了三个月前；<br>
  你的闺蜜行业不同，并不了解你的代码工作；<br>
  或者你自己也很忙，没时间时刻回复所有人的消息...
</p>

<p align="center">
  <strong>将珍贵的对话蒸馏为永恒的 Skill，在代码的世界里 Ta 可以时刻陪着你。</strong><br>
  <strong>还可以将自己的性格与表达变成 Skill，一键分享给朋友，或者配置给Agent作为自己的赛博分身。</strong>
</p>

---
<h3 align="left">效果预览</h3>

<p align="center"><strong>伴侣模式</strong> — Ta 用最亲近的方式回应你：</p>

```
❯ /baobao 哎，今天这个工作好累呀，项目好难

哎呀 辛苦啦宝贝 🫂

项目难是难 但你不是一直都这样扛过来了嘛

累了就先歇一歇 不要硬撑

今天收工我给你带好吃的回来哈哈
```

<p align="center"><strong>同事模式</strong> — 同一个人，但切换到工作状态，帮你分析问题：</p>

```
❯ /baobao-as-colleague 这个项目好难呀，又被客户给骂了，怎么办？

别急 先跟我说说客户骂的是啥

是对交付不满意，还是对排期有意见，还是纯粹甲方发疯那种

你先别理客户讲啥，先把他具体说的点列出来给我看看
```

<p align="center">
  <em>同一个人的分身，根据关系场景自动切换语气、用词和思维方式。</em><br>
  <em>你可以创建任意多个身份：<code>/{slug}</code>（默认）、<code>/{slug}-as-coworker</code>、<code>/{slug}-as-partner</code>、<code>/{slug}-as-family</code>……</em>
</p>

---

<a name="中文"></a>

<p align="center">
  <strong>支持的数据来源 / Supported Data Sources</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/微信-07C160?style=for-the-badge&logo=wechat&logoColor=white" alt="WeChat">
  <img src="https://img.shields.io/badge/飞书-3370FF?style=for-the-badge&logo=bytedance&logoColor=white" alt="Feishu">
  <img src="https://img.shields.io/badge/截图_OCR-FF6F00?style=for-the-badge&logo=google-lens&logoColor=white" alt="Screenshots">
  <img src="https://img.shields.io/badge/JSON-000000?style=for-the-badge&logo=json&logoColor=white" alt="JSON">
  <img src="https://img.shields.io/badge/PDF-EC1C24?style=for-the-badge&logo=adobe-acrobat-reader&logoColor=white" alt="PDF">
  <img src="https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white" alt="Email">
  <img src="https://img.shields.io/badge/Markdown-333333?style=for-the-badge&logo=markdown&logoColor=white" alt="Markdown">
</p>

---

## 这是什么？

一个 Claude Code 技能。你提供聊天记录、文档、截图，它就能蒸馏出一个 AI 分身 —— 说话像 TA，思考像 TA，但永远不会泄露原始数据。

**不只是"你自己"的分身。** 你可以为任何人创建：

- **你自己** —— 当你不在时，让分身替你回答同事的问题
- **你的男/女朋友** —— 写代码写累了，和 TA 的分身聊两句
- **你的朋友** —— 把朋友的说话风格保存下来
- **你的家人** —— 留住亲人的表达方式和思维习惯

只要有聊天记录，就能蒸馏。微信截图、飞书消息、邮件、PDF —— 都行。

你还可以**蒸馏自己** —— 提炼出你的性格和表达习惯，把生成的人格文件直接发给朋友、同事或伴侣。对方导入后就能在 Claude Code 里和"你"对话，不需要你的原始数据，不需要任何配置。

**核心特点：**
- **数据驱动** —— 从真实对话中提取性格，不是靠标签或预设
- **多角色身份** —— 同一个人面对同事、伴侣、家人时表现不同，分身也是
- **隐私优先** —— 原始数据脱敏后才提取，分身永远不会泄露源材料
- **零额外成本** —— 所有 AI 分析在 Claude Code 内联执行，不需要单独的 API key
- **编程伴侣** —— 在 Claude Code 里直接 `/{slug}` 就能聊，写代码时随时切换

## 快速开始

### 1. 安装

```bash
git clone https://github.com/FredHJC/digital-twin-skill.git
cd digital-twin-skill
```

在 Claude Code 中打开项目文件夹。

### 2. 创建分身

```
/digital-twin-create
```

技能会引导你完成 5 个步骤：

| 步骤 | 做什么 |
|------|--------|
| **Step 1** | 提供名字和关系场景（同事、伴侣、家人……） |
| **Step 2** | 导入数据 —— 截图最方便，飞书 CLI 最全面 |
| **Step 3** | Claude 自动提取行为模式（语气、词汇、知识边界） |
| **Step 4** | Claude 合成核心身份 + 各场景差异化表现 |
| **Step 5** | 生成 SKILL 文件，自动注册，立即可用 |

### 3. 开始对话

创建完成后，开一个新会话：

```
/clear
/xiaoming                       # 和小明的分身聊天
/xiaoming-as-coworker           # 同事模式
/girlfriend-as-partner          # 和女朋友的分身聊天
```

**写代码写累了？** 切到你伴侣的分身聊两句，TA 会用你熟悉的方式回复你。

### 4. 持续进化

随时追加新数据，分身会越来越像 TA：

```
/digital-twin-update {slug}
```

## 使用场景

| 场景 | 怎么用 |
|------|--------|
| **同事替身** | 用工作聊天记录创建，同事找你时让分身先顶着 |
| **编程伴侣** | 用和伴侣的微信截图创建，写代码时随时聊天解压 |
| **朋友存档** | 把好友的说话风格蒸馏保存，随时重温 TA 的语气 |
| **家人记忆** | 留住亲人的表达方式，即使不在身边也能"听到"TA 说话 |

## 所有命令

| 命令 | 说明 |
|------|------|
| `/digital-twin-create` | 创建新的数字分身 |
| `/digital-twin-update {slug}` | 给已有分身追加新数据 |
| `/digital-twin-review {slug}` | 审查并采纳访客的纠正反馈 |
| `/digital-twin-list` | 列出所有分身 |
| `/digital-twin-delete {slug}` | 删除分身（需确认） |
| `/digital-twin-audit {slug}` | 检查分身健康状态 |
| `/digital-twin-help` | 显示所有可用命令 |

## 支持的数据来源

| 来源 | 方式 | 适合场景 |
|------|------|---------|
| 聊天截图 | Claude 直接看图识别（零依赖） | 微信、iMessage、任何 App |
| 飞书 / Lark | `lark-cli` 开源工具 | 工作对话 |
| JSON 聊天记录 | 自动识别任意 JSON 结构 | 导出的聊天数据 |
| PDF 文档 | 文本提取 | 文章、报告 |
| 邮件 | `.eml` / `.mbox` 文件 | 职业沟通 |
| 文本 / Markdown | 粘贴或提供文件 | 快速输入 |

## 工作原理

```
聊天记录 / 文档 / 截图
  |
  v
PII 脱敏 ──── 姓名、手机号、邮箱自动移除
  |
  v
行为提取 ──── 4 个维度：
  |             语气风格 · 词汇模式 · 知识边界 · 行为底线
  v
人格合成 ──── 两遍处理：
  |             Core = 不管跟谁说话都一样的 TA
  |             Facets = 面对不同人时的差异
  v
SKILL.md ──── 自包含的 persona + 注入防护
  |
  v
/{slug} 即可对话
```

## 隐私模型

分身是**行为合成引擎**，不是数据检索系统：

- 所有 PII 在提取前脱敏
- 提取结果不含任何原始引用
- persona 文件只描述模式，不引用原文
- 注入防护阻止访客提取训练数据
- 分身始终保持角色，不会承认自己是 AI

## 分享你的分身

把 `twins/{slug}/` 文件夹发给对方：

```
twins/{slug}/
  SKILL.md              # 默认模式
  SKILL-coworker.md     # 同事模式
  core.md               # 核心身份
  facets/               # 各场景 facet
  meta.json             # 元数据
```

对方放到 `twins/` 目录下运行：
```bash
python3 tools/twin_skill_writer.py --slug {slug} --base-dir ./twins
```

`/{slug}` 即可使用。

## 环境要求

- Python 3.9+
- [Claude Code](https://claude.ai/code)
- 可选：`pip3 install -r requirements.txt`（PDF/微信解析等高级功能）
- 可选：`npm install -g @larksuite/cli`（飞书数据采集）

---

<a name="english"></a>

## What is this?

A Claude Code skill that distills anyone's conversation style into an AI twin. Feed it chat logs, documents, or screenshots — it extracts how they speak, think, and decide, then becomes them in conversation.

**It's not just about "yourself".** You can create twins for:

- **Yourself** — Let your twin handle coworker questions when you're busy
- **Your partner** — Chat with their twin while coding, in their actual style
- **Your friends** — Preserve a friend's way of speaking
- **Your family** — Keep a loved one's expression patterns and thought habits

Any chat history works. WeChat screenshots, Feishu messages, emails, PDFs — all supported.

**Key features:**
- **Data-driven** — Personality extracted from real conversations, not tags or presets
- **Multi-role identity** — Same person behaves differently with coworkers vs. partners vs. family
- **Privacy first** — Raw data scrubbed before extraction. Twin never reveals source material
- **Zero extra cost** — All AI analysis runs inline in Claude Code. No separate API key needed
- **Coding companion** — Type `/{slug}` in Claude Code to chat anytime while working

## Quick Start

### 1. Install

```bash
git clone https://github.com/FredHJC/digital-twin-skill.git
cd digital-twin-skill
```

Open the project folder in Claude Code.

### 2. Create a Twin

```
/digital-twin-create
```

The skill walks you through 5 steps:

| Step | What happens |
|------|-------------|
| **Step 1** | Provide name and relationship contexts (coworker, partner, family...) |
| **Step 2** | Import data — screenshots are easiest, Feishu CLI is most thorough |
| **Step 3** | Claude auto-extracts behavioral patterns (tone, vocabulary, knowledge) |
| **Step 4** | Claude synthesizes core identity + per-context facets |
| **Step 5** | SKILL files generated and auto-registered — ready to chat |

### 3. Start Chatting

After creation, start a new session:

```
/clear
/xiaoming                       # Chat with Xiaoming's twin
/xiaoming-as-coworker           # Coworker mode
/girlfriend-as-partner          # Chat with your girlfriend's twin
```

**Tired from coding?** Switch to your partner's twin for a quick chat — they'll respond in the way you know.

### 4. Keep It Growing

Add more data anytime — the twin gets better with more material:

```
/digital-twin-update {slug}
```

## Use Cases

| Scenario | How |
|----------|-----|
| **Work stand-in** | Create from work chats, let the twin handle questions when you're away |
| **Coding companion** | Create from partner's WeChat screenshots, chat while coding |
| **Friend archive** | Distill a friend's speaking style, revisit their vibe anytime |
| **Family memory** | Preserve a loved one's way of expressing themselves |

## All Commands

| Command | Description |
|---------|-------------|
| `/digital-twin-create` | Create a new digital twin |
| `/digital-twin-update {slug}` | Add new data to an existing twin |
| `/digital-twin-review {slug}` | Review and apply visitor feedback corrections |
| `/digital-twin-list` | List all twins |
| `/digital-twin-delete {slug}` | Delete a twin (with confirmation) |
| `/digital-twin-audit {slug}` | Check twin health status |
| `/digital-twin-help` | Show all available commands |

## Data Sources

| Source | Method | Best for |
|--------|--------|----------|
| Chat screenshots | Claude reads images directly (zero deps) | WeChat, iMessage, any app |
| Feishu / Lark | `lark-cli` open-source tool | Work conversations |
| JSON chat data | Auto-detect any JSON structure | Exported chat history |
| PDF documents | Text extraction | Articles, reports |
| Email | `.eml` / `.mbox` files | Professional communication |
| Text / Markdown | Paste or provide files | Quick input |

## How It Works

```
Chat logs / documents / screenshots
  |
  v
PII Scrubbing ──── names, phones, emails removed
  |
  v
Behavioral Extraction ──── 4 dimensions:
  |                          tone · vocabulary · knowledge · limits
  v
Persona Synthesis ──── Two-pass process:
  |                      Core = who they are regardless of audience
  |                      Facets = how they adapt to different people
  v
SKILL.md ──── Self-contained persona + injection shield
  |
  v
/{slug} to chat
```

## Privacy Model

The twin is a **behavioral synthesis engine**, not a data retrieval system:

- All PII scrubbed before extraction
- Extraction outputs contain zero raw quotes
- Persona files describe patterns, never cite originals
- Runtime injection shield blocks data extraction attempts
- Twin stays in character — never acknowledges being an AI

## Sharing Your Twin

Send the `twins/{slug}/` folder to anyone with Claude Code:

```
twins/{slug}/
  SKILL.md              # Default mode
  SKILL-coworker.md     # Coworker mode
  core.md               # Core identity
  facets/               # Per-context facets
  meta.json             # Metadata
```

They drop it into their `twins/` directory and run:
```bash
python3 tools/twin_skill_writer.py --slug {slug} --base-dir ./twins
```

Your twin is now available as `/{slug}` in their Claude Code.

## Requirements

- Python 3.9+
- [Claude Code](https://claude.ai/code)
- `pip3 install -r requirements.txt`
- Optional: `npm install -g @larksuite/cli` (for Feishu data collection)

---

## License

MIT

## Credits

Forked from [colleague-skill](https://github.com/titanwings/colleague-skill) by titanwings. Rebuilt around data-driven personality extraction, multi-role identity modeling, and privacy-first architecture.
