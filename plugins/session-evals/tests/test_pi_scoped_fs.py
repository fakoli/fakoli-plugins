import importlib.util
import os

import pytest


HERE = os.path.dirname(__file__)
PATH = os.path.join(HERE, "..", "scripts", "pi_scoped_fs.py")
spec = importlib.util.spec_from_file_location("scoped_fs", PATH)
scoped_fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoped_fs)


def test_scoped_filesystem_allows_regular_fixture_edit(tmp_path):
    (tmp_path / "answer.txt").write_text("broken\n", encoding="utf-8")
    fs = scoped_fs.ScopedFilesystem(str(tmp_path))
    fs.edit("answer.txt", "broken", "fixed")
    fs.write("new.txt", "new\n")
    assert fs.read("answer.txt") == "fixed\n"
    assert fs.read("new.txt") == "new\n"


@pytest.mark.parametrize("path", ["../oracle.py", "/tmp/oracle.py", "nested/../../oracle.py"])
def test_scoped_filesystem_rejects_path_escapes(tmp_path, path):
    fs = scoped_fs.ScopedFilesystem(str(tmp_path))
    with pytest.raises(scoped_fs.ScopedPathError):
        fs.write(path, "escape")


def test_scoped_filesystem_rejects_symlink_target_and_existing_write_ancestor(tmp_path):
    outside = tmp_path.parent / "oracle.py"
    outside.write_text("trusted\n", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(outside)
    (tmp_path / "linked-dir").symlink_to(tmp_path.parent, target_is_directory=True)
    fs = scoped_fs.ScopedFilesystem(str(tmp_path))
    for action in (lambda: fs.read("link.txt"), lambda: fs.write("link.txt", "bad"),
                   lambda: fs.write("linked-dir/oracle.py", "bad")):
        with pytest.raises(scoped_fs.ScopedPathError):
            action()
    assert outside.read_text(encoding="utf-8") == "trusted\n"
