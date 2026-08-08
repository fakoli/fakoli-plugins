.PHONY: install test lint clean

install:
	@echo "no dependencies (python stdlib only; PyYAML optional)"

test:
	python tests/test_skill_spec_lint.py

lint:
	python -c "import ast,sys; ast.parse(open('scripts/skill_spec_lint.py').read()); ast.parse(open('tests/test_skill_spec_lint.py').read()); print('syntax ok')"

clean:
	@echo "nothing to clean"
