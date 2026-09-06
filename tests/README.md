# FlowSlide Test Suite Index

This directory contains the automated test suites for FlowSlide.

## Test Inventory

| File / Directory | Module | Description |
| :--- | :--- | :--- |
| `tests/test_auth_service.py` | `flowslide.auth` | Unit tests for authentication service, admin bootstrap, credential validation, session invalidation on password change, and username/email uniqueness. |
| `tests/test_passwords.py` | `flowslide.core` | Unit tests for native bcrypt password hashing, 72-byte limit enforcement, legacy `$2a$/$2y$` compatibility, and format validation. |
| `tests/performance/` | Performance | Load and stress test scripts using Locust (`locustfile.py`, `api_performance.py`, `run_performance_tests.py`). |

## Running Tests

Run the full unit test suite using `pytest`:

```bash
pytest
```
