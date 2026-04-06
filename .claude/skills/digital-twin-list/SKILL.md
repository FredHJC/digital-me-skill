---
name: "digital-twin-list"
description: "List all digital twins | 列出所有分身"
version: "1.1.0"
user-invocable: true
allowed-tools: Bash
---

Run:
```bash
PYTHONPATH=. python3 tools/twin_writer.py --action list --base-dir ./twins
```

Format output as table: Name, Slug, Contexts, Version, Created date.
