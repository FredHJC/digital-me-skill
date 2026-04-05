from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

# Ensure tools/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def twin_dir(tmp_path: Path) -> Path:
    """Temporary twins directory for test isolation."""
    d = tmp_path / "twins" / "test-twin"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def sample_chat_csv(tmp_path: Path) -> Path:
    """Synthetic WeChatMsg CSV fixture with known PII content."""
    csv_path = tmp_path / "wechat_export.csv"
    rows = [
        {"StrTalker": "wxid_abc123", "StrContent": "你好，我的手机号是13912345678", "Type": "1", "CreateTime": "1696118400", "IsSender": "1"},
        {"StrTalker": "wxid_abc123", "StrContent": "邮箱是test@example.com", "Type": "1", "CreateTime": "1696118460", "IsSender": "1"},
        {"StrTalker": "wxid_abc123", "StrContent": "收到图片", "Type": "3", "CreateTime": "1696118520", "IsSender": "0"},
        {"StrTalker": "wxid_abc123", "StrContent": "好的没问题", "Type": "1", "CreateTime": "1696118580", "IsSender": "0"},
        {"StrTalker": "wxid_abc123", "StrContent": "明天见", "Type": "1", "CreateTime": "1696118640", "IsSender": "1"},
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["StrTalker", "StrContent", "Type", "CreateTime", "IsSender"])
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


@pytest.fixture
def sample_eml(tmp_path: Path) -> Path:
    """Synthetic .eml file for email parser tests."""
    eml_path = tmp_path / "test.eml"
    eml_content = (
        "From: sender@example.com\r\n"
        "To: recipient@example.com\r\n"
        "Subject: Test Email\r\n"
        "Date: Mon, 1 Jan 2024 10:00:00 +0800\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "你好，请联系我 13800138000 或发邮件到 private@test.com。\r\n"
        "我的身份证号是110101199001011234。\r\n"
    )
    eml_path.write_text(eml_content, encoding="utf-8")
    return eml_path
