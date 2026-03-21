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
        "requests": [],
    }


def _save_log(log: dict) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    COST_LOG_PATH.write_text(json.dumps(log, indent=2))


def record_usage(chars: int, voice_id: str, model_id: str) -> dict:
    """Record a TTS request and return the entry."""
    log = _load_log()
    cost = chars * log.get("cost_per_char", DEFAULT_COST_PER_CHAR)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "characters": chars,
        "cost_usd": round(cost, 6),
        "voice_id": voice_id,
        "model_id": model_id,
    }

    log["total_characters"] += chars
    log["total_cost_usd"] = round(log["total_cost_usd"] + cost, 6)
    log["total_requests"] += 1
    # Keep last 100 requests to avoid unbounded growth
    log["requests"].append(entry)
    log["requests"] = log["requests"][-100:]

    _save_log(log)
    return entry


def get_summary() -> dict:
    """Return usage summary."""
    log = _load_log()
    today = datetime.now(timezone.utc).date().isoformat()
    today_chars = 0
    today_cost = 0.0
    today_requests = 0

    for req in log.get("requests", []):
        req_date = req.get("timestamp", "")[:10]
        if req_date == today:
            today_chars += req.get("characters", 0)
            today_cost += req.get("cost_usd", 0.0)
            today_requests += 1

    return {
        "total_characters": log.get("total_characters", 0),
        "total_cost_usd": round(log.get("total_cost_usd", 0.0), 4),
        "total_requests": log.get("total_requests", 0),
        "today_characters": today_chars,
        "today_cost_usd": round(today_cost, 4),
        "today_requests": today_requests,
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
