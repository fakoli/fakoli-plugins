.PHONY: install test lint clean
install:
	@echo "no dependencies (bash + grep + awk)"
test:
	bash tests/test-scan-cli-hygiene.sh
lint:
	bash -n scripts/scan-cli-hygiene.sh tests/test-scan-cli-hygiene.sh
clean:
	@echo "nothing to clean"
