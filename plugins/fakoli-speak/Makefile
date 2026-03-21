.PHONY: install test lint clean run-speak run-stop run-status run-voices run-cost

install:
	uv sync --all-extras

test:
	uv run pytest -v

lint:
	uv run python -m py_compile src/fakoli_speak/cli.py
	uv run python -m py_compile src/fakoli_speak/tts.py
	uv run python -m py_compile src/fakoli_speak/cost.py

clean:
	rm -rf .venv __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

run-speak:
	@echo "Usage: echo 'text' | uv run fakoli-speak speak"

run-stop:
	uv run fakoli-speak stop

run-status:
	uv run fakoli-speak status

run-voices:
	uv run fakoli-speak voices

run-cost:
	uv run fakoli-speak cost
