from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from tools.ingestion_output import (
    validate_context_label,
    write_ingestion_json,
    BUILTIN_LABELS,
    SCHEMA_VERSION,
)


class TestValidateContextLabel:
    def test_builtin_coworker(self):
        assert validate_context_label("coworker") == "coworker"

    def test_builtin_partner(self):
        assert validate_context_label("partner") == "partner"

    def test_builtin_family(self):
        assert validate_context_label("family") == "family"

    def test_builtin_friend(self):
        assert validate_context_label("friend") == "friend"

    def test_custom_label(self):
        assert validate_context_label("college-roommate") == "college-roommate"

    def test_whitespace_stripped(self):
        assert validate_context_label("  coworker  ") == "coworker"

    def test_case_normalized(self):
        assert validate_context_label("COWORKER") == "coworker"

    def test_empty_exits(self):
        with pytest.raises(SystemExit):
            validate_context_label("")


class TestWriteIngestionJSON:
    def test_creates_json_file(self, tmp_path: Path):
        chunks = [{"id": 0, "text": "hello", "metadata": {}}]
        result = write_ingestion_json(
            chunks=chunks,
            source_type="test",
            context_label="coworker",
            twin_slug="testslug",
            source_file="input.txt",
            scrub_stats={"[PHONE]": 1},
            base_dir=tmp_path / "twins",
        )
        assert result.exists()
        assert result.suffix == ".json"

    def test_json_schema(self, tmp_path: Path):
        chunks = [{"id": 0, "text": "test text", "metadata": {"sender": "self"}}]
        result = write_ingestion_json(
            chunks=chunks,
            source_type="wechat_csv",
            context_label="partner",
            twin_slug="zhangsan",
            source_file="export.csv",
            scrub_stats={"[PHONE]": 2, "[EMAIL]": 1},
            base_dir=tmp_path / "twins",
        )
        doc = json.loads(result.read_text(encoding="utf-8"))
        assert doc["schema_version"] == "1.0"
        assert doc["source_type"] == "wechat_csv"
        assert doc["context_label"] == "partner"
        assert doc["twin_slug"] == "zhangsan"
        assert doc["chunk_count"] == 1
        assert doc["scrub_stats"]["[PHONE]"] == 2
        assert len(doc["chunks"]) == 1

    def test_correct_directory_path(self, tmp_path: Path):
        result = write_ingestion_json(
            chunks=[],
            source_type="email",
            context_label="family",
            twin_slug="myslug",
            source_file="test.eml",
            scrub_stats={},
            base_dir=tmp_path / "twins",
        )
        # Per D-08: knowledge/{context}/
        assert "knowledge" in str(result)
        assert "family" in str(result)
        assert "myslug" in str(result)

    def test_chinese_content_preserved(self, tmp_path: Path):
        chunks = [{"id": 0, "text": "你好世界", "metadata": {}}]
        result = write_ingestion_json(
            chunks=chunks,
            source_type="text",
            context_label="friend",
            twin_slug="test",
            source_file="input.txt",
            scrub_stats={},
            base_dir=tmp_path / "twins",
        )
        content = result.read_text(encoding="utf-8")
        assert "你好世界" in content


class TestBuiltinLabels:
    def test_four_labels(self):
        assert BUILTIN_LABELS == {"coworker", "partner", "family", "friend"}

    def test_schema_version(self):
        assert SCHEMA_VERSION == "1.0"
