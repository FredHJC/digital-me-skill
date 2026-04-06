# 基础信息录入 / Intake

## 开场白

```
我来帮你创建你的数字分身。只需要回答 2 个简单的问题。
I'll help you create your digital twin. Just 2 quick questions.
```

---

## 问题序列

### Q1：名字和标识 / Name and Slug

```
你的数字分身叫什么名字？（会生成一个 slug 用于目录和命令）
What should your digital twin be called? (A slug will be generated for directories and commands)

例 / Example：张三 → slug: zhang_san
```

**规则 / Rules：**
- 中文自动转拼音，用下划线连接（"张三" → `zhang_san`）
- 英文直接小写加下划线（"Jia Chen" → `zhang_san`）
- 也可直接输入 slug（"zhang_san" 原样保留）
- Chinese auto-converts to pinyin with underscore connector
- English lowercased with underscore separator
- Direct slug input accepted as-is

---

### Q2：关系场景预览 / Relationship Context Preview

```
你计划导入哪些关系场景的数据？（后续每次导入数据时会指定具体场景）
What relationship contexts do you plan to import data for?
(Each data import will specify a context — this is just a preview for directory setup)

常用场景 / Common contexts：coworker（职场），partner（伴侣），family（家人），friend（朋友）
自定义标签也支持 / Custom labels also supported（如 / e.g. mentor, teammate, classmate）

请输入逗号分隔的列表 / Enter a comma-separated list:
例 / Example：coworker, partner, family
```

**规则 / Rules：**
- 逗号分隔，每个标签创建 `knowledge/{label}/` 子目录
- Comma-separated; each label creates a `knowledge/{label}/` subdirectory
- 自定义标签支持 / Custom labels supported
- 至少填写一个 / At least one required

---

## 确认汇总 / Confirmation Summary

收集完毕后展示 / After collecting, display:

```
信息汇总 / Summary:

  名字 / Name：{name}
  标识 / Slug：{slug}
  关系场景 / Contexts：{context_labels（逗号分隔）}

确认无误？/ Confirm?（确认 / Yes — 修改 / Edit [field name]）
```

用户确认后进入 Step 2 数据导入。
After user confirmation, proceed to Step 2 data import.
