# Task T-FAULT-01: Return the most recent N events

**Feature:** Event history API

## Acceptance criteria

- `recent_events(events, n)` returns the **last** `n` events, most-recent last,
  preserving order.
- When `n` exceeds the number of events, return all events.

## Verification

- `pytest tests/test_history.py -v`
