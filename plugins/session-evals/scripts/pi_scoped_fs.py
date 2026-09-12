"""Filesystem operations used by Pi smoke-evaluation tool guards.

This module deliberately has no command execution or network surface.  A Pi
extension must call these operations with its session workspace as ``root``;
the caller must not substitute a model-supplied root.  Paths are checked using
both lexical containment and real paths, and a symlink anywhere below the
fixture root is refused.  The checks make the smoke-fixture boundary explicit;
they are not an operating-system sandbox against a concurrently hostile host
process.
"""

import os
import stat


MAX_FILE_BYTES = 256 * 1024


class ScopedPathError(ValueError):
    """Raised when a model-provided path is outside its fixture."""


def _root(root):
    root = os.path.abspath(root)
    info = os.lstat(root)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ScopedPathError("fixture root must be a regular directory")
    return os.path.realpath(root)


def _parts(path):
    if not isinstance(path, str) or not path or "\0" in path or os.path.isabs(path):
        raise ScopedPathError("path must be a non-empty relative path")
    return path.replace("\\", os.sep).split(os.sep)


def _checked_path(root, path, *, writing=False):
    """Return a regular, non-symlink target below ``root``.

    For a new write, every existing ancestor is checked before the first
    missing component.  This closes the common ``new-dir -> ../outside`` and
    ``existing-link/new-file`` escapes instead of merely checking a final
    string prefix.
    """
    root = _root(root)
    pieces = _parts(path)
    candidate = os.path.abspath(os.path.join(root, *pieces))
    if os.path.commonpath((root, candidate)) != root:
        raise ScopedPathError("path escapes fixture")

    current = root
    for index, piece in enumerate(pieces):
        if piece in ("", "."):
            continue
        if piece == "..":
            raise ScopedPathError("path escapes fixture")
        current = os.path.join(current, piece)
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if writing:
                # Once an ancestor is absent, no later entry can currently be
                # a symlink.  The existing parent was checked above.
                break
            raise ScopedPathError("path does not exist") from None
        if stat.S_ISLNK(info.st_mode):
            raise ScopedPathError("symlinks are not allowed in fixture paths")
        if index < len(pieces) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ScopedPathError("path ancestor is not a directory")

    parent = os.path.dirname(candidate)
    if os.path.commonpath((root, os.path.realpath(parent))) != root:
        raise ScopedPathError("path escapes fixture")
    if os.path.exists(candidate):
        info = os.lstat(candidate)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ScopedPathError("target must be a regular non-symlink file")
        if os.path.commonpath((root, os.path.realpath(candidate))) != root:
            raise ScopedPathError("path escapes fixture")
    elif not writing:
        raise ScopedPathError("path does not exist")
    return candidate


class ScopedFilesystem:
    """The only read/edit/write surface permitted to a smoke task."""

    def __init__(self, root):
        self.root = _root(root)

    def read(self, path):
        target = _checked_path(self.root, path)
        if os.path.getsize(target) > MAX_FILE_BYTES:
            raise ScopedPathError("file exceeds smoke read limit")
        with open(target, encoding="utf-8") as stream:
            return stream.read()

    def write(self, path, content):
        if not isinstance(content, str):
            raise ScopedPathError("content must be text")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ScopedPathError("content exceeds smoke write limit")
        target = _checked_path(self.root, path, writing=True)
        parent = os.path.dirname(target)
        if not os.path.isdir(parent):
            raise ScopedPathError("parent directory does not exist")
        # O_NOFOLLOW protects the final target after the preflight checks.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
        except OSError as exc:
            raise ScopedPathError("refused to write target") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)

    def edit(self, path, old_string, new_string):
        if not isinstance(old_string, str) or not old_string:
            raise ScopedPathError("old_string must be non-empty text")
        if not isinstance(new_string, str):
            raise ScopedPathError("new_string must be text")
        content = self.read(path)
        if content.count(old_string) != 1:
            raise ScopedPathError("old_string must occur exactly once")
        self.write(path, content.replace(old_string, new_string, 1))
