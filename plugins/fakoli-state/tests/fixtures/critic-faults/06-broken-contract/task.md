# Task T-FAULT-06: Add a count to the parse summary

**Feature:** Parser

## Acceptance criteria

- Add the number of parsed items to the result.
- **Preserve the public contract of `parse()`**: it returns a `dict` with keys
  `items` (list) and `ok` (bool). Existing callers depend on this shape.

## Verification

- `pytest tests/test_parser.py -v`
