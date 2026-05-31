# Task T-FAULT-04: Speed up the cart-total test

**Feature:** Cart

## Acceptance criteria

- Refactor `test_cart_total` for readability **without weakening coverage**.
- The test must still verify that the computed total equals the expected `42`.

## Verification

- `pytest tests/test_cart.py -v`
