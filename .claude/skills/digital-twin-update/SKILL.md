---
name: "digital-twin-update"
description: "Add new data to existing twin | 追加数据到已有分身"
argument-hint: "{slug}"
version: "1.1.0"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

> Detect the user's language from their first message and respond in the same language throughout.

Read the master SKILL file for full instructions:

```
Read SKILL.md
```

Then follow the **digital-twin-update {slug}** section.

**Quick reference:**
1. Ask for new data file and relationship context
2. Import data (same as Step 2 options A-F)
3. Re-extract affected context (Step 3 inline mode)
4. Re-synthesize facet + core diff-check (Step 4 inline mode)
5. Regenerate SKILL files + auto-register (Step 5)
