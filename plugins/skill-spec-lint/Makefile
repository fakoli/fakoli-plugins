.PHONY: install test lint clean

install:
	@echo "Run with uv run --script; PyYAML is declared in the script"

test:
	uv run --with pyyaml python tests/test_skill_spec_lint.py
	uv run --with pyyaml python -m unittest discover -s tests -p 'test_yaml_contract.py'

lint:
	python -c "import ast,sys; ast.parse(open('scripts/skill_spec_lint.py').read()); ast.parse(open('tests/test_skill_spec_lint.py').read()); print('syntax ok')"

clean:
	@echo "nothing to clean"
