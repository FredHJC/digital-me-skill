# 安装指南 / Installation Guide

## 依赖安装 / Install Dependencies（可选）

大部分功能无需额外安装。如需使用 PDF 解析、微信导出等高级功能：

```bash
pip3 install -r requirements.txt
```

## 飞书 CLI 配置 / Feishu CLI Setup（推荐 / Recommended）

```bash
# 安装 lark-cli
npm install -g @larksuite/cli

# 初始化应用配置（按提示在飞书开放平台创建应用）
lark-cli config init

# 用户授权登录（自动选择常用权限）
lark-cli auth login --recommend

# 验证
lark-cli contact +get-user --as user
```

## 其他平台配置 / Other Platform Setup

Each data collector requires its own credentials. Run `--setup` for first-time config:

- Feishu API (legacy): `python3 tools/feishu_auto_collector.py --setup --context dummy --slug dummy`
- DingTalk: `python3 tools/dingtalk_auto_collector.py --setup`
- Slack: `python3 tools/slack_auto_collector.py --setup`

Credentials are stored in `~/.digital-twin/`.
