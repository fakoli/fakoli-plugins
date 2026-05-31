# Task T-FAULT-02: Load timeout from optional config

**Feature:** Config loading

## Acceptance criteria

- `get_timeout(config)` returns `config.timeout` when present.
- When `config` is `None` (no config file found), return the default `30`.
  This path is explicitly exercised on first run before any config exists.

## Verification

- `pytest tests/test_config.py -v`
