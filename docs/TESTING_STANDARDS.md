# Plugin Testing Standards

Guidelines for plugin authors writing tests in the fakoli-plugins ecosystem.

---

## When to add tests

Add a `tests/` directory for any plugin that ships Python scripts. If the plugin
has a `src/` tree or an MCP server entry point, it needs tests.

---

## Directory structure

```
plugins/my-plugin/
├── src/
├── tests/
│   ├── __init__.py          # empty, marks tests as a package
│   ├── conftest.py          # shared fixtures
│   ├── test_core.py         # unit tests for core logic
│   └── test_integration.py  # optional: end-to-end / subprocess tests
├── pyproject.toml
└── Makefile
```

pytest discovers every file matching `test_*.py` under `tests/`.

---

## pyproject.toml configuration

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Standard Makefile targets

Every plugin Makefile must expose at minimum:

```makefile
install:
    uv sync --all-extras

test:
    uv run pytest -v

lint:
    uv run python -m py_compile src/<package>/*.py

clean:
    rm -rf .venv __pycache__ .pytest_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
```

Run `make install` once, then `make test` on every change.

---

## Patterns from fakoli-speak

### Fixtures (conftest.py)

Define reusable objects once; pytest injects them by argument name.

```python
# tests/conftest.py
import pytest
from mypackage.client import Client

@pytest.fixture
def client():
    return Client(api_key="test-key", dry_run=True)
```

### Monkeypatching

Replace external calls without a real network or file system.

```python
def test_fetch_uses_cache(monkeypatch, client):
    called = {}

    def fake_get(url, **kwargs):
        called["url"] = url
        return FakeResponse(200, b"hello")

    monkeypatch.setattr("httpx.get", fake_get)
    result = client.fetch("https://example.com")
    assert result == "hello"
    assert called["url"] == "https://example.com"
```

### Mocking MCP tool handlers

For MCP servers, test the handler function directly — no transport needed.

```python
import pytest
from myserver.server import handle_fetch

@pytest.mark.asyncio
async def test_handle_fetch_strips_script_tags(monkeypatch):
    async def fake_http_get(url):
        return "<html><script>alert(1)</script><p>Safe</p></html>"

    monkeypatch.setattr("myserver.server.http_get", fake_http_get)
    result = await handle_fetch(url="https://example.com")
    assert "<script>" not in result
    assert "Safe" in result
```

### Parametrize for attack vectors / edge cases

```python
@pytest.mark.parametrize("payload,expected", [
    ("<script>evil()</script>", ""),
    ("Normal text", "Normal text"),
    ("\u200b\u200c invisible", "invisible"),  # zero-width chars stripped
])
def test_sanitize(payload, expected):
    from myserver.sanitizer import sanitize
    assert sanitize(payload) == expected
```

---

## CI expectations

- All tests must pass with `make test` from the plugin directory.
- Tests must not make real network requests; monkeypatch all I/O.
- Aim for coverage of every public function and each documented attack vector.
- Keep individual test functions short; extract helpers if setup exceeds ~10 lines.
