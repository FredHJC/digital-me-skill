from __future__ import annotations

from tools.pii_scrubber import scrub, PLACEHOLDER_TYPES


class TestChinesePhone:
    def test_mobile_plain(self):
        text, stats = scrub("手机号13812345678联系我")
        assert "[PHONE]" in text
        assert "13812345678" not in text
        assert stats.get("[PHONE]", 0) >= 1

    def test_mobile_with_86_prefix(self):
        text, stats = scrub("电话+8613912345678")
        assert "[PHONE]" in text
        assert stats.get("[PHONE]", 0) >= 1

    def test_landline(self):
        text, stats = scrub("座机010-12345678")
        assert "[PHONE]" in text
        assert stats.get("[PHONE]", 0) >= 1


class TestEmail:
    def test_standard_email(self):
        text, stats = scrub("邮箱test@example.com联系")
        assert "[EMAIL]" in text
        assert "test@example.com" not in text
        assert stats.get("[EMAIL]", 0) >= 1

    def test_email_with_dots(self):
        text, stats = scrub("发到first.last@company.co.uk")
        assert "[EMAIL]" in text


class TestNationalID:
    def test_18_digit_id(self):
        text, stats = scrub("身份证号110101199001011234")
        assert "[ID_NUMBER]" in text
        assert "110101199001011234" not in text
        assert stats.get("[ID_NUMBER]", 0) >= 1

    def test_id_with_x(self):
        text, stats = scrub("证件11010119900101123X")
        assert "[ID_NUMBER]" in text


class TestBankAccount:
    def test_19_digit_card(self):
        text, stats = scrub("卡号 6222021234567890123 转账")
        assert "[BANK_ACCOUNT]" in text
        assert stats.get("[BANK_ACCOUNT]", 0) >= 1

    def test_16_digit_card(self):
        text, stats = scrub("卡号 6222021234567890 转账")
        assert "[BANK_ACCOUNT]" in text


class TestDOB:
    def test_chinese_format(self):
        text, stats = scrub("出生日期1990年1月1日")
        assert "[DOB]" in text
        assert stats.get("[DOB]", 0) >= 1

    def test_dash_format(self):
        text, stats = scrub("生日1990-01-15")
        assert "[DOB]" in text


class TestNoFalsePositives:
    def test_names_not_scrubbed(self):
        """Per D-03: Names are NOT scrubbed by regex (deferred to LLM fallback)."""
        text, stats = scrub("张三是个好同事")
        assert text == "张三是个好同事"

    def test_company_names_not_scrubbed(self):
        """Per D-03: Company names are NOT scrubbed."""
        text, stats = scrub("字节跳动的项目经理")
        assert text == "字节跳动的项目经理"

    def test_job_titles_not_scrubbed(self):
        """Per D-03: Job titles are NOT scrubbed."""
        text, stats = scrub("高级后端工程师")
        assert text == "高级后端工程师"

    def test_project_names_not_scrubbed(self):
        """Per D-03: Project names are NOT scrubbed."""
        text, stats = scrub("飞书文档项目")
        assert text == "飞书文档项目"


class TestMultiplePII:
    def test_mixed_pii(self):
        text, stats = scrub("联系我13812345678或test@example.com，身份证110101199001011234")
        assert "[PHONE]" in text
        assert "[EMAIL]" in text
        assert "[ID_NUMBER]" in text
        assert "13812345678" not in text
        assert "test@example.com" not in text

    def test_stats_counts(self):
        text, stats = scrub("号码13800000001和13900000002")
        assert stats.get("[PHONE]", 0) == 2


class TestLLMFallback:
    def test_stub_returns_unchanged(self):
        """Phase 1: LLM fallback is a no-op stub."""
        text, stats = scrub("张三在北京海淀区中关村", use_llm_fallback=True)
        # Stub does not modify text (address/name detection deferred)
        assert "张三" in text


class TestPlaceholderTypes:
    def test_all_declared(self):
        assert "[PHONE]" in PLACEHOLDER_TYPES
        assert "[EMAIL]" in PLACEHOLDER_TYPES
        assert "[ID_NUMBER]" in PLACEHOLDER_TYPES
        assert "[BANK_ACCOUNT]" in PLACEHOLDER_TYPES
        assert "[DOB]" in PLACEHOLDER_TYPES
        assert "[NAME]" in PLACEHOLDER_TYPES
        assert "[ADDRESS]" in PLACEHOLDER_TYPES
