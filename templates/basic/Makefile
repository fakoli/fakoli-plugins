.PHONY: install test lint clean

install:
	uv sync --all-extras

test:
	uv run pytest -v

lint:
	uv run python -m py_compile src/**/*.py

clean:
	rm -rf .venv __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
