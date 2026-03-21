"""Tests for CLI module."""

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from fakoli_speak import cli


class TestCmdSpeak:
    @patch("fakoli_speak.cli.tts")
    def test_speaks_from_args(self, mock_tts):
        mock_tts.speak.return_value = {
            "characters": 5,
            "cost_usd": 0.0015,
            "voice_id": "v1",
            "model_id": "m1",
        }
        args = cli.argparse.Namespace(text=["hello", "world"])
        cli.cmd_speak(args)
        mock_tts.speak.assert_called_once_with("hello world")

    @patch("fakoli_speak.cli.tts")
    def test_speaks_from_stdin(self, mock_tts, monkeypatch):
        mock_tts.speak.return_value = {
            "characters": 9,
            "cost_usd": 0.003,
            "voice_id": "v1",
            "model_id": "m1",
        }
        monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
        args = cli.argparse.Namespace(text=[])
        cli.cmd_speak(args)
        mock_tts.speak.assert_called_once_with("from stdin")

    def test_exits_when_no_input(self, monkeypatch):
        mock_stdin = MagicMock()
        mock_stdin.isatty.return_value = True
        monkeypatch.setattr("sys.stdin", mock_stdin)
        args = cli.argparse.Namespace(text=[])
        with pytest.raises(SystemExit):
            cli.cmd_speak(args)


class TestCmdCost:
    @patch("fakoli_speak.cli.cost")
    def test_shows_summary(self, mock_cost, capsys):
        mock_cost.get_summary.return_value = {
            "total_characters": 5000,
            "total_cost_usd": 1.50,
            "total_requests": 10,
            "today_characters": 1000,
            "today_cost_usd": 0.30,
            "today_requests": 3,
            "cost_per_1k_chars": 0.30,
        }
        args = cli.argparse.Namespace(reset=False, rate=None, json=False)
        cli.cmd_cost(args)
        captured = capsys.readouterr()
        assert "5,000 chars" in captured.out
        assert "$1.5000" in captured.out
        assert "10 requests" in captured.out

    @patch("fakoli_speak.cli.cost")
    def test_reset(self, mock_cost):
        args = cli.argparse.Namespace(reset=True, rate=None, json=False)
        cli.cmd_cost(args)
        mock_cost.reset_usage.assert_called_once()

    @patch("fakoli_speak.cli.cost")
    def test_set_rate(self, mock_cost):
        args = cli.argparse.Namespace(reset=False, rate=0.11, json=False)
        cli.cmd_cost(args)
        mock_cost.set_cost_rate.assert_called_once_with(0.11)

    @patch("fakoli_speak.cli.cost")
    def test_json_output(self, mock_cost, capsys):
        mock_cost.get_summary.return_value = {"total_requests": 5}
        args = cli.argparse.Namespace(reset=False, rate=None, json=True)
        cli.cmd_cost(args)
        captured = capsys.readouterr()
        assert '"total_requests": 5' in captured.out
