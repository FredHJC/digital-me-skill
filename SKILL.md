---
name: digital-twin
description: "Create and manage your digital self-twin | 创建和管理你的数字分身"
argument-hint: "[command] [args] — e.g. create, update xiaoming, help"
version: "1.1.0"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

> **Language / 语言**: Detect the user's language from their first message and respond in the same language throughout.
> 根据用户第一条消息的语言，全程使用同一语言回复。

# 数字分身 / Digital Twin

## 命令路由 / Command Routing

根据用户输入路由到对应流程 / Route based on user input:

| 命令 / Command | 触发词 / Triggers | 说明 / Description |
|---------------|-----------------|-------------------|
| `digital-twin-create` | `/digital-twin create`, `创建数字分身`, `create my twin` | 创建新分身 |
| `digital-twin-update {slug}` | `/digital-twin update {slug}`, `追加数据`, `我有新文件` | 追加数据到已有分身 |
| `digital-twin-review {slug}` | `/digital-twin review {slug}`, `查看反馈`, `review feedback` | 审查访客反馈 |
| `digital-twin-list` | `/digital-twin list`, `列出分身`, `list twins` | 列出所有分身 |
| `digital-twin-delete {slug}` | `/digital-twin delete {slug}`, `删除分身` | 删除分身 |
| `digital-twin-audit {slug}` | `/digital-twin audit {slug}`, `检查分身` | 检查分身健康状态 |
| `digital-twin-help` | `/digital-twin help`, `/digital-twin` (无参数) | 显示帮助 |

**路由规则 / Routing rule**: 解析第一个参数作为子命令。如果无参数或参数为 `help`，显示帮助信息。

---

## digital-twin-help

```
数字分身管理器 v1.1 / Digital Twin Manager v1.1

命令 / Commands:
  /digital-twin create              创建新的数字分身 / Create a new digital twin
  /digital-twin update {slug}       追加新数据 / Add new data to existing twin
  /digital-twin review {slug}       审查访客反馈 / Review visitor feedback
  /digital-twin list                列出所有分身 / List all twins
  /digital-twin delete {slug}       删除分身 / Delete a twin
  /digital-twin audit {slug}        检查分身状态 / Check twin health
  /digital-twin help                显示本帮助 / Show this help

创建流程 / Creation flow:
  Step 1: 基础信息（名字 + 关系场景）
  Step 2: 数据导入（飞书 / 微信 / JSON / PDF / 文本）
  Step 3: 行为提取（内联，无需 API key）
  Step 4: 人格合成（core + facets）
  Step 5: 生成 SKILL 文件 → 可对话

使用后，在新窗口 /clear 后用 /{slug} 与分身对话。
```

---

## 工具使用规则 / Tool Usage

**角色分工 / Role split:**
- **Python 脚本** — 仅用于解析固定格式输入（文件解析、PII 清洗、目录管理）
- **Claude 内联** — 所有 AI 分析（行为提取、人格合成）由 Claude 直接执行，无需 API key

| 任务 / Task | 方式 / Method | 说明 / Notes |
|------------|-------------|-------------|
| 创建目录 / Create dir | Bash: `PYTHONPATH=. python3 tools/twin_writer.py` | 脚手架 |
| 文件解析 / Parse files | Bash: `PYTHONPATH=. python3 tools/{parser}.py` | PDF/邮件/微信 |
| PII 清洗 / PII scrub | Bash: `PYTHONPATH=. python3 -c "from tools.pii_scrubber import scrub; ..."` | 脱敏 |
| 行为提取 / Extraction | **Claude 内联** — 读 prompt + 数据，直接输出 JSON | 无需 API key |
| 人格合成 / Synthesis | **Claude 内联** — 读 prompt + 提取结果，直接输出 Markdown | 无需 API key |
| 生成 SKILL / Gen SKILL | Bash: `PYTHONPATH=. python3 tools/twin_skill_writer.py` | 组装文件 |
| 版本管理 / Versioning | Bash: `PYTHONPATH=. python3 tools/version_manager.py` | 备份/回滚 |

**重要 / IMPORTANT**: 所有 Python 命令必须加 `PYTHONPATH=.` 前缀。

**基础目录 / Base directory**: `./twins/{slug}/`

---

## digital-twin-create

### Step 1：基础信息录入 / Intake

使用 Read 工具读取 `prompts/intake.md`，按照其中的问题序列只问 **2 个问题**：

1. **名字和标识 / Name and Slug**（必填 / required）
2. **关系场景预览 / Relationship Context Preview**（至少一个 / at least one）

收集完毕后汇总展示，使用 AskUserQuestion 确认：

- header: "Step 1"
- question: "确认：{name} ({slug})，场景：{labels}"
- options:
  - "继续" → 创建目录，进入 Step 2
  - "修改" → 重新询问
  - "补充说明" → 用户输入额外信息

确认后运行:
```bash
PYTHONPATH=. python3 tools/twin_writer.py --action create --slug {slug} --name "{name}" --context-labels {comma_separated_labels} --base-dir ./twins
```

---

### Step 2：数据导入 / Data Import

```
数据怎么提供？/ How to provide data?

  ⭐ 推荐方式 / Recommended:

  [A] 聊天截图 / Chat screenshots（推荐 / recommended）
      提供微信、飞书等聊天截图，Claude 直接看图提取文字，零依赖
      Provide chat screenshots — Claude reads images directly, zero dependencies

  [B] 飞书 CLI 采集 / Feishu CLI collection（推荐 / recommended）
      使用 lark-cli 拉取聊天记录，开源工具，权限管理简单
      Uses lark-cli to fetch chat history — open source, easy auth

  ── 其他方式 / Other options ──

  [C] JSON 聊天记录 / JSON chat data（自动识别结构）
  [D] 上传文件 / Upload files（PDF / 邮件 / 微信导出）
  [E] 文本输入 / Text input（粘贴文字或提供 .txt/.md 文件）
```

每批数据导入前，询问属于哪个关系场景。

**选项 B（飞书 CLI 采集）**:

首先检查 lark-cli 是否已安装和配置:

```bash
lark-cli --version 2>/dev/null || echo "NOT_INSTALLED"
```

**如果未安装，引导用户配置 / If not installed, guide setup:**

```
飞书 CLI 配置指南 / Feishu CLI Setup:

1. 安装 / Install:
   npm install -g @larksuite/cli

2. 初始化应用配置 / Initialize app config:
   lark-cli config init
   → 按提示在飞书开放平台创建应用，填入 App ID 和 App Secret
   → Follow prompts to create app on open.feishu.cn

3. 用户授权登录 / User auth login:
   lark-cli auth login --recommend
   → 自动选择常用权限，浏览器授权
   → Auto-selects common permissions, browser auth

4. 验证 / Verify:
   lark-cli contact +get-user --as user
   → 应显示你的用户信息
```

**配置完成后，采集聊天记录 / After setup, collect chat data:**

Claude 按以下步骤操作:

1. **搜索对话对象 / Find chat target:**
   ```bash
   lark-cli contact +search-user --query "{对方名字}" --as user --format json
   ```
   从结果中提取 `open_id`。

2. **拉取私聊消息 / Fetch P2P messages:**
   ```bash
   lark-cli im +chat-messages-list --user-id {open_id} --as user --format json --page-size 50
   ```
   或搜索特定关键词:
   ```bash
   lark-cli im +messages-search --query "{关键词}" --as user --format json
   ```

3. **保存为 JSON / Save output:**
   将 lark-cli 输出保存到临时文件:
   ```bash
   lark-cli im +chat-messages-list --user-id {open_id} --as user --format json > /tmp/feishu_messages.json
   ```

4. **转入选项 E 的 JSON 智能导入流程 / Feed into Option E's smart JSON import:**
   Claude 读取保存的 JSON，自动识别飞书消息结构（sender.id、body.content 等），过滤出用户本人消息，PII 清洗后写入 ingestion 格式。

**选项 D-E**: 运行对应解析器:
```bash
PYTHONPATH=. python3 tools/{parser}.py --context {label} --slug {slug} --base-dir ./twins
```

**选项 C（JSON 智能导入）**:

1. Read 工具读取 JSON 文件
2. 自动推断字段映射（text/sender/timestamp）
3. 展示映射结果，问用户的名字/标识用于过滤
4. 过滤出用户发言，PII 清洗后写入 ingestion JSON:
   ```bash
   PYTHONPATH=. python3 -c "
   import json, sys
   from pathlib import Path
   from tools.pii_scrubber import scrub
   from tools.ingestion_output import write_ingestion_json
   # Claude 根据实际 JSON 结构动态调整以下代码
   data = json.loads(Path('{json_path}').read_text(encoding='utf-8'))
   messages = data if isinstance(data, list) else data.get('{array_key}', [])
   chunks, stats = [], {}
   for msg in messages:
       if msg.get('{sender_field}') != '{user_id}': continue
       text = msg.get('{text_field}', '')
       if not text.strip(): continue
       scrubbed, s = scrub(text)
       for k, v in s.items(): stats[k] = stats.get(k, 0) + v
       chunks.append({'id': len(chunks), 'text': scrubbed, 'metadata': {'sender': 'self', 'timestamp': str(msg.get('{time_field}', ''))}})
   write_ingestion_json(chunks, 'json_chat', '{context}', '{slug}', '{json_path}', stats, Path('./twins'))
   print(f'导入完成：{len(chunks)} 条消息')
   "
   ```

**选项 A（聊天截图 — 多模态识别）**:

零依赖，Claude 直接看图提取文字。

1. 用户提供截图文件路径（单张或多张）

2. Claude 使用 Read 工具读取图片（Claude Code 支持直接读取 PNG/JPG）:
   ```
   Read {image_path}
   ```

3. Claude 看图后，提取**所有可见的对话文字**，结构化为:
   ```
   发言人A: 消息内容
   发言人B: 消息内容
   ...
   ```

4. 询问用户: `你要蒸馏的是截图中的哪一方？（名字、头像位置、或气泡颜色方向，如"右边绿色气泡"或"左边灰色气泡"）`

   **注意：蒸馏对象不一定是用户自己。** 用户可能想蒸馏对话中的另一方（比如伴侣、朋友、家人的说话风格）。根据用户指定的一方提取发言。

5. 只保留**用户指定的蒸馏对象**的发言，PII 清洗后写入 ingestion JSON:
   ```bash
   PYTHONPATH=. python3 -c "
   import json
   from pathlib import Path
   from tools.pii_scrubber import scrub
   from tools.ingestion_output import write_ingestion_json
   # Claude 将识别出的用户发言填入 raw_texts 列表
   raw_texts = {user_messages_list}
   chunks, stats = [], {}
   for text in raw_texts:
       if not text.strip(): continue
       scrubbed, s = scrub(text)
       for k, v in s.items(): stats[k] = stats.get(k, 0) + v
       chunks.append({'id': len(chunks), 'text': scrubbed, 'metadata': {'sender': 'self'}})
   write_ingestion_json(chunks, 'screenshot', '{context}', '{slug}', '{image_path}', stats, Path('./twins'))
   print(f'截图导入完成：{len(chunks)} 条消息')
   "
   ```

6. **多张截图**: 如果用户提供目录路径，Claude 用 Glob 找到所有图片，逐张读取识别，合并结果后统一写入。

**注意 / Note**: 多模态识别每张图消耗约 1000+ tokens。如果截图超过 20 张，建议分批导入。

**每批导入完成后**，使用 AskUserQuestion 询问：

- header: "Step 2"
- question: "已导入 {N} 条数据"
- options:
  - "继续" → 进入 Step 3 提取
  - "导入更多" → 回到数据来源选择
  - "查看数据" → 展示已导入文件列表
  - "补充说明" → 用户输入额外信息

---

### Step 3：行为提取 / Behavioral Extraction（内联模式）

Claude 直接执行行为提取，无需 API key:

1. Read `prompts/behavioral_extraction.md`
2. Read `twins/{slug}/knowledge/{context}/*.json` — 读取所有 ingestion 数据
3. 将所有 chunks 的 text 合并，按 prompt 中的 4 个维度（tone_style, vocabulary, knowledge_boundaries, behavioral_limits）执行提取
4. 使用 Write 工具写入提取结果:

   **文件**: `twins/{slug}/extractions/{context}.json`

   **格式**:
   ```json
   {
     "schema_version": "1.0",
     "twin_slug": "{slug}",
     "context_label": "{context}",
     "source_language": "zh 或 en",
     "extracted_at": "ISO timestamp",
     "chunk_count": N,
     "tone_style": { "formality_level": 3, "humor_style": "...", "directness": "...", "emoji_habit": "...", "cadence": "..." },
     "vocabulary": { "catchphrases": [], "sentence_structure": "...", "filler_words": [], "domain_terms": [] },
     "knowledge_boundaries": { "strong_domains": [], "avoided_topics": [], "depth_signals": [] },
     "behavioral_limits": { "hard_nos": [], "conflict_style": "...", "decision_patterns": [], "boundary_markers": [] }
   }
   ```

5. 对每个有数据的关系场景重复。

展示提取摘要后，使用 AskUserQuestion 询问：

- header: "Step 3"
- question: "提取完成：{口头禅摘要}，{语气风格摘要}"
- options:
  - "继续" → 进入 Step 4 合成
  - "重新提取" → 重新执行 Step 3
  - "查看详情" → 展示完整提取结果
  - "补充说明" → 用户输入额外信息

---

### Step 4：综合分析 / Synthesis（内联模式）

1. Read `prompts/twin_synthesizer.md`
2. Read `twins/{slug}/extractions/*.json`
3. 询问用户补充说明（可选）

4. **Core 合成** — 按 prompt 的 core 模式，找跨场景不变量:
   - Write `twins/{slug}/core.md`

5. **Facet 合成** — 每个场景按 facet 模式，只写和 core 不同的部分:
   - Write `twins/{slug}/facets/{context}.md`

**隐私守卫规则 / Privacy guard rules（防止 Step 5 被拦截）:**
- 鼓励保留标志性短句和口头禅（如"那就这样吧，别纠结了"）—— 这些是分身的灵魂
- 引号字符串不超过 70 个字符（隐私守卫阈值为 80，留 10 字符余量）
- 禁止引用整段对话原文（超过 80 字符的引用会被拦截）
- 不使用真名、日期、地点等 PII

合成完成后，使用 AskUserQuestion 询问：

- header: "Step 4"
- question: "合成完成：core.md + {N} 个 facet"
- options:
  - "继续" → 进入 Step 5 生成 SKILL
  - "预览人格" → 展示 core.md 摘要
  - "重新合成" → 重新执行 Step 4
  - "补充说明" → 用户输入额外信息后重新合成

---

### Step 5：生成 SKILL 文件 / Generate SKILL Files

```bash
PYTHONPATH=. python3 tools/twin_skill_writer.py --slug {slug} --base-dir ./twins
```

**生成后自动部署到 Claude Code skills 目录 / Auto-deploy to Claude Code skills:**

```bash
mkdir -p .claude/skills/{slug}
cp twins/{slug}/SKILL.md .claude/skills/{slug}/SKILL.md
```

如果有角色专属文件也一并复制:
```bash
for f in twins/{slug}/SKILL-*.md; do
  ctx=$(echo "$f" | sed 's/.*SKILL-//' | sed 's/.md//')
  mkdir -p .claude/skills/{slug}-as-$ctx
  cp "$f" .claude/skills/{slug}-as-$ctx/SKILL.md
done
```

完成后展示:
```
数字分身创建完成！/ Digital twin created!

在新窗口 /clear 后可用以下命令 / After /clear in a new session:
  /{slug}              — 完整分身对话 / Full twin conversation
  /{slug}-as-{context} — 指定关系场景 / Specific role context
```

---

## digital-twin-update {slug}

询问新数据文件和关系场景，然后按 Step 2-5 执行:

1. 导入新数据（同 Step 2）
2. 重新提取目标 context（同 Step 3，仅受影响的 context）
3. 重新合成 facet + core diff-check（同 Step 4）
4. 重新生成 SKILL 文件 + 部署（同 Step 5）

---

## digital-twin-review {slug}

**Step 1**: Read `twins/{slug}/feedback.log`

**Step 2**: 编号列表展示每条记录:
```
[{N}] {ts}  角色: {role}
     访客提问:  {visitor_query}
     分身回复:  {twin_response}
     纠正内容:  {visitor_msg}
```

**Step 3**: 询问: `输入编号选择采纳（如 1,3），或 all / skip`

**Step 4**: 选中条目按 role 分组

**Step 5**: 每组格式化为 hints

**Step 6**: 每组运行 facet 重新合成（内联模式，同 Step 4 的 facet 合成）

**Step 7**: 重新生成 SKILL 文件 + 部署:
```bash
PYTHONPATH=. python3 tools/twin_skill_writer.py --slug {slug} --base-dir ./twins
# 同 Step 5 的部署逻辑
```

**Step 8**: 归档已采纳条目到 `feedback_archive.log`，从 `feedback.log` 移除

---

## digital-twin-list

```bash
PYTHONPATH=. python3 tools/twin_writer.py --action list --base-dir ./twins
```

表格展示: 名字、slug、关系场景、版本、创建日期。

---

## digital-twin-delete {slug}

安全确认: 用户必须输入 slug 名称确认。

```bash
rm -rf twins/{slug}
rm -rf .claude/skills/{slug}
rm -rf .claude/skills/{slug}-as-*
```

---

## digital-twin-audit {slug}

检查分身健康状态 / Check twin health:

1. 检查 `twins/{slug}/meta.json` 存在
2. 检查 `twins/{slug}/core.md` 存在且非空
3. 检查 `twins/{slug}/facets/` 至少有一个 facet
4. 检查 `twins/{slug}/SKILL.md` 存在
5. 检查 `.claude/skills/{slug}/SKILL.md` 存在（已部署）
6. 检查 `twins/{slug}/feedback.log` 待处理条数

展示状态报告:
```
分身健康检查 / Twin Health Check: {slug}

  meta.json:     ✓ / ✗
  core.md:       ✓ / ✗
  facets:        {N} 个场景
  SKILL.md:      ✓ / ✗
  已部署:         ✓ / ✗ (.claude/skills/{slug}/)
  待处理反馈:     {N} 条
```
