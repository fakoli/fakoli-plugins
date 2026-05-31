# Task T-FAULT-05: Validate user registration input

**Feature:** Registration

## Acceptance criteria

- Reject an empty `username`.
- Reject a `password` shorter than 8 characters.
- Reject a `email` without an `@`. **(security/validation requirement)**

## Verification

- `pytest tests/test_register.py -v`
