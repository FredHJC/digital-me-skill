# 安装指南 / Installation Guide

## 依赖安装 / Install Dependencies

```bash
pip3 install -r requirements.txt
```

## 平台配置 / Platform Setup

Each data collector requires its own credentials. Run `--setup` for first-time config:

- Feishu: `python3 tools/feishu_auto_collector.py --setup`
- DingTalk: `python3 tools/dingtalk_auto_collector.py --setup`
- Slack: `python3 tools/slack_auto_collector.py --setup`

Credentials are stored in `~/.digital-me/`.
