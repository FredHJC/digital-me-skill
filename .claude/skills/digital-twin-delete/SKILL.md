---
name: "digital-twin-delete"
description: "Delete a digital twin | 删除分身"
argument-hint: "{slug}"
version: "1.1.0"
user-invocable: true
allowed-tools: Bash
---

> Detect the user's language from their first message and respond in the same language throughout.

**Safety gate**: Ask user to type the slug name to confirm deletion.

Only proceed if input matches slug exactly:

```bash
rm -rf twins/{slug}
rm -rf .claude/skills/{slug}
rm -rf .claude/skills/{slug}-as-*
```

Show confirmation: `已删除数字分身 {slug} / Digital twin {slug} has been deleted.`
