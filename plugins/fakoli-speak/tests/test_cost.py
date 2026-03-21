"""Tests for cost tracking module."""

import json
import os
from pathlib import Path

import pytest

from fakoli_speak import cost


@pytest.fixture(autouse=True)
def temp_cost_log(tmp_path, monkeypatch):
    """Use a temporary file for cost logging."""
    log_path = tmp_path / "test-usage.json"
    monkeypatch.setattr(cost, "COST_LOG_PATH", log_path)
    return log_path


class TestRecordUsage:
    def test_records_first_request(self):
        entry = cost.record_usage(500, "voice123", "model456")
        assert entry["characters"] == 500
        assert entry["cost_usd"] > 0
        assert entry["voice_id"] == "voice123"
        assert entry["model_id"] == "model456"
        assert "timestamp" in entry

    def test_accumulates_totals(self):
        cost.record_usage(100, "v1", "m1")
        cost.record_usage(200, "v1", "m1")

        summary = cost.get_summary()
        assert summary["total_characters"] == 300
        assert summary["total_requests"] == 2

    def test_cost_calculation(self):
        entry = cost.record_usage(1000, "v1", "m1")
        # Default rate is $0.30/1K chars = $0.0003/char
        assert abs(entry["cost_usd"] - 0.30) < 0.001

    def test_caps_request_history_at_100(self, temp_cost_log):
        for i in range(110):
            cost.record_usage(10, "v1", "m1")

        log = json.loads(temp_cost_log.read_text())
        assert len(log["requests"]) == 100
        # But totals still reflect all 110
        assert log["total_requests"] == 110
        assert log["total_characters"] == 1100


class TestGetSummary:
    def test_empty_log(self):
        summary = cost.get_summary()
        assert summary["total_characters"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["total_requests"] == 0
        assert summary["today_requests"] == 0

    def test_today_tracking(self):
        cost.record_usage(500, "v1", "m1")
        summary = cost.get_summary()
        assert summary["today_characters"] == 500
        assert summary["today_requests"] == 1

    def test_includes_rate(self):
        summary = cost.get_summary()
        assert summary["cost_per_1k_chars"] == 0.3


class TestSetCostRate:
    def test_updates_rate(self):
        cost.set_cost_rate(0.11)  # Growth plan
        summary = cost.get_summary()
        assert abs(summary["cost_per_1k_chars"] - 0.11) < 0.001

    def test_new_rate_applies_to_future_requests(self):
        cost.set_cost_rate(0.10)  # $0.10/1K
        entry = cost.record_usage(1000, "v1", "m1")
        assert abs(entry["cost_usd"] - 0.10) < 0.001


class TestResetUsage:
    def test_resets_all_data(self):
        cost.record_usage(500, "v1", "m1")
        cost.reset_usage()

        summary = cost.get_summary()
        assert summary["total_characters"] == 0
        assert summary["total_requests"] == 0


class TestCorruptedLog:
    def test_handles_corrupted_json(self, temp_cost_log):
        temp_cost_log.write_text("not json{{{")
        summary = cost.get_summary()
        assert summary["total_characters"] == 0

    def test_handles_missing_fields(self, temp_cost_log):
        temp_cost_log.write_text("{}")
        # Should not crash
        entry = cost.record_usage(100, "v1", "m1")
        assert entry["characters"] == 100
