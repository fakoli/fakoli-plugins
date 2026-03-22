"""Cost tracking for multi-provider TTS usage."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Fallback cost rate used when neither a per-provider override nor a
# provider-supplied rate is available.
DEFAULT_COST_PER_CHAR = 0.00030  # $0.30 per 1K characters (ElevenLabs Starter plan)

COST_LOG_PATH = Path(os.environ.get(
    "FAKOLI_SPEAK_COST_LOG",
    os.path.expanduser("~/.claude/fakoli-speak-usage.json"),
))


def _load_log() -> dict:
    if COST_LOG_PATH.exists():
        try:
            data = json.loads(COST_LOG_PATH.read_text())
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
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=COST_LOG_PATH.parent, suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(log, f, indent=2)
        os.replace(tmp_path, COST_LOG_PATH)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _get_cost_per_char(provider_name: str) -> float:
    """Resolve the cost-per-character for *provider_name*.

    Resolution order:
    1. Per-provider override stored in the cost log.
    2. The provider's own default cost rate from the registry.
    3. The module-level fallback constant.
    """
    log = _load_log()
    overrides = log.get("cost_per_char_overrides", {})
    if provider_name in overrides:
        return overrides[provider_name]
    try:
        from . import registry  # noqa: PLC0415
        p = registry.get_provider(provider_name)
        return p.get_default_cost_rate().cost_per_1k_chars / 1000.0
    except Exception:
        return DEFAULT_COST_PER_CHAR


def record_usage(
    chars: int,
    voice_id: str,
    model_id: str,
    provider: str,
) -> dict:
    """Record a TTS request and return the entry dict."""
    log = _load_log()
    cost_per_char = _get_cost_per_char(provider)
    cost_usd = chars * cost_per_char
    today = datetime.now(timezone.utc).date().isoformat()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "characters": chars,
        "cost_usd": round(cost_usd, 6),
        "voice_id": voice_id,
        "model_id": model_id,
        "provider": provider,
    }

    # All-time running totals
    log["total_characters"] += chars
    log["total_cost_usd"] = round(log["total_cost_usd"] + cost_usd, 6)
    log["total_requests"] += 1

    # Daily running totals (reset on date change)
    if log.get("today_date") != today:
        log["today_date"] = today
        log["today_characters"] = 0
        log["today_cost_usd"] = 0.0
        log["today_requests"] = 0
    log["today_characters"] += chars
    log["today_cost_usd"] = round(log["today_cost_usd"] + cost_usd, 6)
    log["today_requests"] += 1

    # Keep last 100 requests for detail view
    log["requests"].append(entry)
    log["requests"] = log["requests"][-100:]

    _save_log(log)
    return entry


def get_summary() -> dict:
    """Return usage summary including the active provider name."""
    from . import registry  # noqa: PLC0415

    log = _load_log()
    today = datetime.now(timezone.utc).date().isoformat()

    if log.get("today_date") == today:
        today_chars = log.get("today_characters", 0)
        today_cost = log.get("today_cost_usd", 0.0)
        today_reqs = log.get("today_requests", 0)
    else:
        today_chars = 0
        today_cost = 0.0
        today_reqs = 0

    try:
        provider_name = registry.get_provider().name
    except Exception:
        provider_name = "unknown"

    return {
        "provider": provider_name,
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


def set_cost_rate(cost_per_1k_chars: float, provider: str | None = None) -> None:
    """Update the cost-per-character rate for *provider* (defaults to active provider)."""
    if provider is None:
        from . import registry  # noqa: PLC0415
        provider = registry.get_provider().name
    log = _load_log()
    overrides = log.setdefault("cost_per_char_overrides", {})
    overrides[provider] = cost_per_1k_chars / 1000.0
    _save_log(log)


def reset_usage() -> None:
    """Reset all usage data."""
    _save_log(_empty_log())
