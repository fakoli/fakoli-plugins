import json
from pathlib import Path

import pytest

import generate
import validate


@pytest.mark.parametrize('source', [
    '# class TestReal:\n#    def test_it(self): pass\n',
    'class TestReal: pass\nclass Wrong:\n    def test_it(self): pass\n',
    'text = "class TestReal: def test_it(self): pass"\n',
])
def test_proof_requires_real_nested_definitions(tmp_path, source):
    file = tmp_path / 'test_proof.py'
    file.write_text(source)
    with pytest.raises(validate.ValidationError, match='symbol'):
        validate._check_proof_symbols('P1', 'test_proof.py::TestReal::test_it', file)


def test_proof_cannot_escape_checkout_via_symlink(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    outside = tmp_path / 'test_external.py'
    outside.write_text('def test_it(): pass\n')
    (root / 'test_link.py').symlink_to(outside)
    for path in ['test_link.py', '../test_external.py', str(outside)]:
        with pytest.raises(validate.ValidationError, match='escapes'):
            validate._confined_path(root, path)


def test_installed_generator_uses_explicit_ledger_and_output(tmp_path, good_ledger):
    data = tmp_path / 'ledger.json'
    output = tmp_path / 'report.md'
    data.write_text(json.dumps(good_ledger))
    assert generate.main(['--data', str(data), '--output', str(output)]) == 0
    assert output.read_text() == generate.render(good_ledger)
    before = output.stat().st_mtime_ns
    assert generate.main(['--data', str(data), '--output', str(output), '--check']) == 0
    assert output.stat().st_mtime_ns == before


def test_custom_data_does_not_silently_overwrite_bundled_doc(tmp_path):
    with pytest.raises(SystemExit) as exc:
        generate.main(['--data', str(tmp_path / 'ledger.json')])
    assert exc.value.code == 2


def test_explicit_evidence_root_is_respected(tmp_path):
    assert validate.resolve_repo_root(tmp_path) == tmp_path.resolve()
