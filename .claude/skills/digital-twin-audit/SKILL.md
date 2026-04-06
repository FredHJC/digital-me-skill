---
name: "digital-twin-audit"
description: "Check twin health status | 检查分身状态"
argument-hint: "{slug}"
version: "1.1.0"
user-invocable: true
allowed-tools: Read, Bash, Glob
---

> Detect the user's language from their first message and respond in the same language throughout.

Check the following for `twins/{slug}/`:

1. `meta.json` exists
2. `core.md` exists and non-empty
3. `facets/` has at least one facet file
4. `SKILL.md` exists
5. `.claude/skills/{slug}/SKILL.md` exists (registered)
6. `feedback.log` pending entry count

Show status report:
```
分身健康检查 / Twin Health Check: {slug}

  meta.json:     ✓ / ✗
  core.md:       ✓ / ✗
  facets:        {N} 个场景
  SKILL.md:      ✓ / ✗
  已部署:         ✓ / ✗ (.claude/skills/{slug}/)
  待处理反馈:     {N} 条
```
