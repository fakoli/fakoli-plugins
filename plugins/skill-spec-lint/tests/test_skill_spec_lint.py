#!/usr/bin/env python3
"""Offline tests for skill_spec_lint. No pytest dependency: plain asserts, run
with `python tests/test_skill_spec_lint.py`. Builds skill dirs in a tmp tree.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import skill_spec_lint as ssl  # noqa: E402


def _skill(root: Path, name: str, frontmatter: str, body: str = "# body\n") -> Path:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\n%s\n---\n%s" % (frontmatter, body), encoding="utf-8")
    return d


def _levels(findings):
    return [(f.level, f.message) for f in findings]


def _msgs(findings):
    return " || ".join(f.message for f in findings)


def run():
    checks = []

    def check(cond, label):
        checks.append((bool(cond), label))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # --- a fully valid skill produces no findings ---------------------
        good = _skill(root, "good-skill", 'name: good-skill\ndescription: "Does a thing. Use when the user asks."')
        f = ssl.validate_skill(good)
        check(f == [], "valid skill -> no findings (got: %s)" % _msgs(f))

        # --- name must match directory ------------------------------------
        d = _skill(root, "dir-name", "name: other-name\ndescription: x")
        f = ssl.validate_skill(d)
        check(any("must match its directory" in m for _, m in _levels(f)), "name!=dir flagged")

        # --- name charset: uppercase, leading/trailing/double hyphen ------
        for bad in ("Bad-Name", "-lead", "trail-", "double--hyphen", "under_score"):
            d = _skill(root, bad, "name: %s\ndescription: x" % bad)
            f = ssl.validate_skill(d)
            # dir name is also `bad`, so the charset error is what we assert on
            check(
                any("lowercase alnum" in m for _, m in _levels(f)),
                "bad name charset flagged: %s" % bad,
            )

        # --- name length > 64 ---------------------------------------------
        long_name = "a" * 65
        d = _skill(root, long_name, "name: %s\ndescription: x" % long_name)
        f = ssl.validate_skill(d)
        check(any("exceeds 64" in m for _, m in _levels(f)), "name >64 flagged")

        # --- description length > 1024 ------------------------------------
        d = _skill(root, "long-desc", "name: long-desc\ndescription: %s" % ("x" * 1025))
        f = ssl.validate_skill(d)
        check(any("description is 1025 chars" in m for _, m in _levels(f)), "description >1024 flagged")

        # --- missing name / description -----------------------------------
        d = _skill(root, "no-desc", "name: no-desc")
        f = ssl.validate_skill(d)
        check(any("missing required `description`" in m for _, m in _levels(f)), "missing description flagged")

        # --- body over the 500-line ceiling -------------------------------
        d = _skill(root, "big-body", "name: big-body\ndescription: x", body="\n".join("l" for _ in range(501)))
        f = ssl.validate_skill(d)
        check(any("body is 501 lines" in m for _, m in _levels(f)), "body >500 lines flagged")

        # --- body exactly at the ceiling is fine --------------------------
        d = _skill(root, "edge-body", "name: edge-body\ndescription: x", body="\n".join("l" for _ in range(500)))
        f = ssl.validate_skill(d)
        check(not any("body is" in m for _, m in _levels(f)), "body ==500 lines not flagged")

        # --- no frontmatter block -----------------------------------------
        d = root / "skills" / "no-front"
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text("# just prose, no frontmatter\n", encoding="utf-8")
        f = ssl.validate_skill(d)
        check(any("frontmatter" in m for _, m in _levels(f)), "missing frontmatter flagged")

        # --- compatibility over 500 chars ---------------------------------
        d = _skill(root, "compat", 'name: compat\ndescription: x\ncompatibility: "%s"' % ("c" * 501))
        f = ssl.validate_skill(d)
        check(any("compatibility is 501" in m for _, m in _levels(f)), "compatibility >500 flagged")

        # --- unknown key is a WARN, not an ERROR --------------------------
        d = _skill(root, "extra-key", "name: extra-key\ndescription: x\nbogus: 1")
        f = ssl.validate_skill(d)
        check(
            any(lvl == "WARN" and "unknown frontmatter key" in m for lvl, m in _levels(f)),
            "unknown key -> WARN",
        )
        check(not any(lvl == "ERROR" for lvl, m in _levels(f)), "unknown key does not ERROR")

        # --- block-scalar description length (folded `>`) -----------------
        folded = "name: folded\ndescription: >\n  " + ("x " * 600)
        d = _skill(root, "folded", folded)
        f = ssl.validate_skill(d)
        check(any("description is" in m and "exceeds 1024" in m for _, m in _levels(f)), "folded desc measured")

        # --- discovery: nested SKILL.md is flagged as undiscoverable ------
        nested = root / "skills" / "good-skill" / "sub"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "SKILL.md").write_text("---\nname: sub\ndescription: x\n---\n", encoding="utf-8")
        dirs, disc = ssl.discover(root)
        check(any("not an immediate child" in f.message for f in disc), "nested SKILL.md flagged")
        check(all(p.name != "sub" for p in dirs), "nested skill not in discoverable set")

        # --- lint() exit semantics: errors -> nonzero ---------------------
        findings, count = ssl.lint([str(root)])
        has_err = any(f.level == "ERROR" for f in findings)
        check(has_err, "repo scan surfaces the seeded errors")
        check(count >= 10, "discovered every seeded immediate skill (count=%d)" % count)

        # --- a SKILL.md-less skill dir is an ERROR, not silently skipped ---
        empty = root / "skills" / "empty-skill"
        empty.mkdir(parents=True, exist_ok=True)
        dirs, _ = ssl.discover(root)
        check(any(p.name == "empty-skill" for p in dirs), "SKILL.md-less dir is a candidate")
        f = ssl.validate_skill(empty)
        check(any("no SKILL.md" in m for _, m in _levels(f)), "SKILL.md-less dir -> ERROR")
        findings2, _ = ssl.lint([str(root)])
        check(
            any("no SKILL.md" in x.message and "empty-skill" in x.path for x in findings2),
            "repo scan surfaces the empty skill dir (not a silent 0)",
        )

        # --- SKILL.md that is a directory is an ERROR ----------------------
        dskill = root / "skills" / "dir-md"
        (dskill / "SKILL.md").mkdir(parents=True, exist_ok=True)
        f = ssl.validate_skill(dskill)
        check(any("is not a file" in m for _, m in _levels(f)), "SKILL.md-as-directory -> ERROR")

        # --- a UTF-8 BOM must not fake a missing frontmatter block ---------
        bom = root / "skills" / "bom-skill"
        bom.mkdir(parents=True, exist_ok=True)
        (bom / "SKILL.md").write_bytes(
            b"\xef\xbb\xbf---\nname: bom-skill\ndescription: fine\n---\n# body\n"
        )
        f = ssl.validate_skill(bom)
        check(f == [], "BOM-prefixed valid skill -> no findings (got: %s)" % _msgs(f))

        # --- fallback parser parity with PyYAML on the bounded fields ------
        # These are the divergences that would flip a length verdict by machine:
        # an inline `# comment` on a plain scalar, and a multi-line plain scalar.
        cases = [
            "name: c1\ndescription: hello world  # trailing comment",
            "name: c2\ndescription: first line\n  continued onto a second",
            'name: c3\ndescription: "quoted # not a comment"',
        ]
        for src in cases:
            fb = ssl._parse_scalars(src)
            if ssl._HAVE_YAML:
                import yaml as _y

                auth = _y.safe_load(src)
                check(
                    fb.get("description") == auth.get("description"),
                    "fallback matches PyYAML description for %r (fb=%r auth=%r)"
                    % (src.split(chr(10))[1], fb.get("description"), auth.get("description")),
                )

        # --- validate through the FORCED fallback path (no PyYAML) ---------
        # PyYAML is present in most envs, so pin the scalar-parser path too:
        # a clean skill passes and an over-length description is caught the
        # same way, proving the "runs on any machine" claim end to end.
        saved = ssl._HAVE_YAML
        try:
            ssl._HAVE_YAML = False
            d = _skill(root, "fb-clean", 'name: fb-clean\ndescription: "works with no yaml"')
            check(ssl.validate_skill(d) == [], "forced-fallback: clean skill passes")
            d = _skill(root, "fb-long", "name: fb-long\ndescription: %s" % ("y" * 1025))
            f = ssl.validate_skill(d)
            check(
                any("description is 1025 chars" in m for _, m in _levels(f)),
                "forced-fallback: over-length description caught",
            )
        finally:
            ssl._HAVE_YAML = saved

        # --- a clean-only path exits 0 ------------------------------------
        with tempfile.TemporaryDirectory() as clean:
            croot = Path(clean)
            _skill(croot, "only-good", 'name: only-good\ndescription: "clean"')
            rc = ssl.main([str(croot)])
            check(rc == 0, "clean tree exits 0")

    failed = [label for ok, label in checks if not ok]
    for ok, label in checks:
        print(("ok   - " if ok else "FAIL - ") + label)
    print("%d passed, %d failed" % (len(checks) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
