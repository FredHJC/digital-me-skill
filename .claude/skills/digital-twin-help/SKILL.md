---
name: "digital-twin-help"
description: "Show all digital twin commands | 显示数字分身帮助"
version: "1.1.0"
user-invocable: true
allowed-tools: Read
---

```
数字分身管理器 v1.1 / Digital Twin Manager v1.1

命令 / Commands:
  /digital-twin-create              创建新的数字分身 / Create a new digital twin
  /digital-twin-update {slug}       追加新数据 / Add new data to existing twin
  /digital-twin-review {slug}       审查访客反馈 / Review visitor feedback
  /digital-twin-list                列出所有分身 / List all twins
  /digital-twin-delete {slug}       删除分身 / Delete a twin
  /digital-twin-audit {slug}        检查分身状态 / Check twin health
  /digital-twin-help                显示本帮助 / Show this help

创建流程 / Creation flow:
  Step 1: 基础信息（名字 + 关系场景）
  Step 2: 数据导入（飞书 / 微信 / JSON / PDF / 截图 / 文本）
  Step 3: 行为提取（内联，无需 API key）
  Step 4: 人格合成（core + facets）
  Step 5: 生成 SKILL 文件 → 可对话

使用后，在新窗口 /clear 后用 /{slug} 与分身对话。
```
