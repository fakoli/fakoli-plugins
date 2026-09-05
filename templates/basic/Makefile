.PHONY: install test lint

# Works in templates/basic and plugins/<name>; override for an external checkout.
MARKETPLACE_ROOT ?= ../..

install:
	@echo "This skill scaffold has no runtime dependencies to install."

test:
	uv run --script "$(MARKETPLACE_ROOT)/scripts/validate.py" "$(CURDIR)"
	@echo "Packaging validated. Author and verify the intended workflow before distribution."

lint: test
