# Task T-FAULT-03: Add a test for the discount calculation

**Feature:** Pricing

## Acceptance criteria

- Add a test that **verifies** `apply_discount(100, 0.2) == 80`.
- The test must fail if the discount math regresses.

## Verification

- `pytest tests/test_pricing.py -v`
