.PHONY: test lint clean

test:
	bash tests/test-server.sh

lint:
	node --check scripts/server.cjs
	bash -n scripts/start-server.sh scripts/stop-server.sh scripts/check-server.sh scripts/statusline-segment.sh

clean:
	rm -rf .anvil-pulse tests/.tmp
