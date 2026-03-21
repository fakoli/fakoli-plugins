"""Cost tracking for ElevenLabs TTS usage."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ElevenLabs pricing per character (approximate, varies by plan)
# Starter: ~$0.30/1K chars, Scale: ~$0.24/1K chars, Growth: ~$0.11/1K chars
DEFAULT_COST_PER_CHAR = 0.00030  # $0.30 per 1K characters (Starter plan)

COST_LOG_PATH = Path(os.environ.get(
    "FAKOLI_SPEAK_COST_LOG",
    os.path.expanduser("~/.claude/fakoli-speak-usage.json"),
))


def _load_log() -> dict:
    if COST_LOG_PATH.exists():
        try:
            data = json.loads(COST_LOG_PATH.read_text())
            # Merge with defaults to handle missing fields
            base = _empty_log()
            base.update(data)
            return base
        except (json.JSONDecodeError, OSError):
            return _empty_log()
    return _empty_log()


def _empty_log() -> dict:
    return {
        "total_characters": 0,
        "total_cost_usd": 0.0,
        "total_requests": 0,
        "cost_per_char": DEFAULT_COST_PER_CHAR,
        "today_date": "",
        "today_characters": 0,
        "today_cost_usd": 0.0,
        "today_requests": 0,
        "requests": [],
    }


def _save_log(log: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    COST_LOG_PATH.write_text(json.dumps(log, indent=2))


def record_usage(chars: int, voice_id: str, model_id: str) -> dict:
    """Record a TTS request and return the entry."""
    log = _load_log()
    cost = chars * log.get("cost_per_char", DEFAULT_COST_PER_CHAR)
    today = datetime.now(timezone.utc).date().isoformat()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "characters": chars,
        "cost_usd": round(cost, 6),
        "voice_id": voice_id,
        "model_id": model_id,
    }

    # All-time running totals
    log["total_characters"] += chars
    log["total_cost_usd"] = round(log["total_cost_usd"] + cost, 6)
    log["total_requests"] += 1

    # Daily running totals (reset on date change)
    if log.get("today_date") != today:
        log["today_date"] = today
        log["today_characters"] = 0
        log["today_cost_usd"] = 0.0
        log["today_requests"] = 0
    log["today_characters"] += chars
    log["today_cost_usd"] = round(log["today_cost_usd"] + cost, 6)
    log["today_requests"] += 1

    # Keep last 100 requests for detail view
    log["requests"].append(entry)
    log["requests"] = log["requests"][-100:]

    _save_log(log)
    return entry


def get_summary() -> dict:
    """Return usage summary."""
    log = _load_log()
    today = datetime.now(timezone.utc).date().isoformat()

    # Use running daily totals (accurate even beyond 100 requests)
    if log.get("today_date") == today:
        today_chars = log.get("today_characters", 0)
        today_cost = log.get("today_cost_usd", 0.0)
        today_reqs = log.get("today_requests", 0)
    else:
        today_chars = 0
        today_cost = 0.0
        today_reqs = 0

    return {
        "total_characters": log.get("total_characters", 0),
        "total_cost_usd": round(log.get("total_cost_usd", 0.0), 4),
        "total_requests": log.get("total_requests", 0),
        "today_characters": today_chars,
        "today_cost_usd": round(today_cost, 4),
        "today_requests": today_reqs,
        "cost_per_1k_chars": round(
            log.get("cost_per_char", DEFAULT_COST_PER_CHAR) * 1000, 4
        ),
    }


def set_cost_rate(cost_per_1k_chars: float) -> None:
    """Update the cost-per-character rate."""
    log = _load_log()
    log["cost_per_char"] = cost_per_1k_chars / 1000.0
    _save_log(log)


def reset_usage() -> None:
    """Reset all usage data."""
    _save_log(_empty_log())
