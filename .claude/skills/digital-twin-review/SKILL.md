---
name: "digital-twin-review"
description: "Review visitor feedback | 审查访客反馈"
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

Then follow the **digital-twin-review {slug}** section (8-step feedback review flow).

**Quick reference:**
1. Read `twins/{slug}/feedback.log`
2. Show numbered list with three-tuple context (visitor query, twin response, correction)
3. Ask owner which to apply (by number, or all/skip)
4. Group by role, format as hints
5. Re-synthesize affected facets (inline mode)
6. Regenerate SKILL files
7. Archive applied entries to `feedback_archive.log`
