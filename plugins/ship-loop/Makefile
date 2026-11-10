.PHONY: install test lint clean

install:
	@echo "no dependencies to install (stdlib-only checker)"

test:
	python3 -m unittest discover -s tests -p 'test_*.py' -q
	bash tests/test-dispatch-packet-sections.sh

lint:
	python3 -m py_compile scripts/verify-delivery.py

clean:
	@echo "nothing to clean"
