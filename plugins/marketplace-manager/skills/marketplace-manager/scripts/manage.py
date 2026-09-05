#!/usr/bin/env python3
"""Manage a chosen Fakoli-compatible source checkout, even from an installed plugin."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
SHARED = ['.claude-plugin/marketplace.json', '.agents/plugins/marketplace.json',
          'registry/index.json', 'registry/categories.json', 'registry/tags.json', 'README.md']


def resolve_root(explicit=None):
    chosen = explicit or os.environ.get('FAKOLI_MARKETPLACE_ROOT')
    start = Path(chosen).expanduser().resolve() if chosen else Path.cwd().resolve()
    candidates = [start] if chosen else [start, *start.parents]
    for root in candidates:
        if (root / '.claude-plugin/marketplace.json').is_file():
            for required in ('scripts/catalog.py', 'scripts/validate.sh', 'scripts/validate.py', 'templates/basic'):
                if not (root / required).exists():
                    raise ValueError(f'{root} lacks {required}; select an updated Fakoli checkout with --root')
            return root
    raise ValueError('No marketplace checkout found. Pass --root /path/to/fakoli-plugins or run from that checkout.')


def load_catalog(root):
    spec = importlib.util.spec_from_file_location('target_catalog', root / 'scripts/catalog.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def transaction(root):
    for relative in SHARED:
        if not (root / relative).resolve().is_relative_to(root):
            raise ValueError(f'Shared artifact escapes the checkout: {relative}')
    lock = root / '.marketplace-manager.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f'Another operation owns {lock}; check its process before removing a stale lock')
    try:
        (lock / 'pid').write_text(str(os.getpid()))
        snapshots = {p: (root / p).read_bytes() if (root / p).exists() else None for p in SHARED}
        try:
            yield
        except BaseException:
            for relative, data in snapshots.items():
                target = root / relative
                if data is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            raise
    finally:
        shutil.rmtree(lock)


def validate(root, target=None):
    subprocess.run(['bash', str(root / 'scripts/validate.sh'), *([str(target)] if target else [])], cwd=root, check=True)
    subprocess.run(['uv', 'run', '--script', str(root / 'scripts/validate.py'),
                    *([str(target)] if target else [])], cwd=root, check=True)


def check_name(name):
    if not NAME.fullmatch(name) or len(name) > 64:
        raise ValueError('Name must be 1–64 lowercase letters/digits separated by single hyphens')


def add(root, name, description, category, no_validate=False):
    check_name(name)
    catalog = load_catalog(root)
    destination = root / 'plugins' / name
    if not destination.resolve().is_relative_to(root):
        raise ValueError('Plugin destination escapes the checkout')
    if destination.exists() or destination.is_symlink():
        raise ValueError(f'Plugin already exists: {name}')
    for relative in SHARED[:2]:
        if (root / relative).exists() and any(p['name'] == name for p in catalog.read_json(root / relative)['plugins']):
            raise ValueError(f'Plugin already registered: {name}')
    with transaction(root):
        try:
            shutil.copytree(root / 'templates/basic', destination)
            owner = catalog.read_json(root / '.claude-plugin/marketplace.json').get('owner', {'name': 'Fakoli'})
            author = {k: v for k, v in owner.items() if k in ('name','email','url')}
            for host in ('claude', 'codex'):
                path = destination / f'.{host}-plugin/plugin.json'
                data = catalog.read_json(path)
                data.update(name=name, description=description, author=author)
                if host == 'codex':
                    data['interface'].update(displayName=name.replace('-', ' ').title(), shortDescription=description,
                                             longDescription=description, developerName=author['name'], category=category,
                                             defaultPrompt=[f'Use {name} to help with this project.'])
                catalog.atomic_json(path, data)
            example = destination / 'skills/example'
            skill = destination / 'skills' / name
            example.rename(skill)
            (skill / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {json.dumps(description)}\n---\n\n'
                f'# {name.replace("-", " ").title()}\n\n'
                'This scaffold has no domain workflow yet. When invoked, state that setup is incomplete and help the user '
                'define its intended inputs, concrete output, and verification steps before claiming the capability is available.\n')
            (destination / 'README.md').write_text(f'# {name}\n\n{description}\n\n'
                f'Edit `skills/{name}/SKILL.md` with the workflow before distributing this scaffold.\n')
            if not no_validate:
                validate(root, destination)
            readme = root / 'README.md'
            content = readme.read_text()
            marker = '<!-- plugin-list:end -->'
            row = f'| [{name}](plugins/{name}) | {description.replace(chr(10), " ").replace("|", "&#124;")} |\n'
            if marker not in content:
                raise ValueError('Root README lacks <!-- plugin-list:end -->; add a plugin table marker before scaffolding')
            readme.write_text(content.replace(marker, row + marker))
            manifest_file = root / '.claude-plugin/marketplace.json'
            marketplace = catalog.read_json(manifest_file)
            category_id = category.lower().replace(' ', '-')
            marketplace['plugins'].append({'name': name, 'source': './plugins/' + name, 'category': category_id})
            catalog.atomic_json(manifest_file, marketplace)
            catalog.generate(root)
        except BaseException:
            if destination.exists():
                shutil.rmtree(destination)
            raise
    print(f'Created scaffold: {destination}. Add the domain workflow before publishing.')


def remove(root, name, force=False):
    check_name(name)
    candidates = [root / folder / name for folder in ('plugins', 'external_plugins')]
    matches = [p for p in candidates if p.exists() or p.is_symlink()]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one local plugin named {name}; found {len(matches)}')
    target = matches[0]
    if target.is_symlink() or not target.resolve().is_relative_to(root):
        raise ValueError('Refusing to remove a symlink or path outside the checkout')
    if not force:
        raise ValueError(f'Removal would delete {target}. Pass --force for this explicit deletion; no files changed.')
    catalog = load_catalog(root)
    with transaction(root), tempfile.TemporaryDirectory(prefix='.marketplace-remove-', dir=root) as temporary:
        backup = Path(temporary) / name
        target.rename(backup)
        try:
            for relative in SHARED[:2]:
                file = root / relative
                if file.exists():
                    data = catalog.read_json(file)
                    data['plugins'] = [p for p in data['plugins'] if p['name'] != name]
                    catalog.atomic_json(file, data)
            readme = root / 'README.md'
            plugin_link = re.compile(r'\]\((?:\./)?(?:plugins|external_plugins)/' + re.escape(name) + r'/?\)')
            readme.write_text(''.join(line for line in readme.read_text().splitlines(keepends=True)
                                      if not (line.lstrip().startswith('|') and plugin_link.search(line))))
            catalog.generate(root)
        except BaseException:
            backup.rename(target)
            raise
    print(f'Removed {name}; catalogs and README synchronized.')


def workflows(root, target, force=False):
    source = Path(__file__).resolve().parent.parent / 'assets/workflows'
    destination = Path(target).expanduser().resolve() if target else root
    for required in ('scripts/validate.sh', 'scripts/validate.py', 'scripts/catalog.py', 'scripts/generate-index.sh', 'scripts/test.sh', 'scripts/check-all.sh', 'scripts/check-registry-drift.sh', 'scripts/check-changelogs.sh', 'tools/plugin-creator/scripts/validate_plugin.py'):
        if not (destination / required).is_file():
            raise ValueError(f'Target lacks {required}; workflows require an updated Fakoli-compatible checkout')
    files = sorted(source.glob('*.yml'))
    if not files:
        raise ValueError('Packaged workflow templates are missing')
    output = destination / '.github/workflows'
    if not output.resolve().is_relative_to(destination) or any(
            path.is_symlink() for path in (destination / '.github', output)):
        raise ValueError('Workflow directory must be a real directory inside the target checkout')
    for file in files:
        dest = output / file.name
        if dest.is_symlink() or not dest.resolve().is_relative_to(destination):
            raise ValueError(f'Workflow output must be a confined regular file: {dest}')
        if dest.exists() and dest.read_bytes() != file.read_bytes() and not force:
            raise ValueError(f'{dest} differs; pass --force to replace it. No workflows changed.')
    output.mkdir(parents=True, exist_ok=True)
    for file in files:
        shutil.copyfile(file, output / file.name)
    print(f'Installed {len(files)} workflows at {output}')


def scan(root, name=None):
    targets = []
    if name:
        check_name(name)
        matches = [root / folder / name for folder in ('plugins', 'external_plugins')
                   if (root / folder / name).is_dir()]
        if len(matches) != 1 or not matches[0].resolve().is_relative_to(root):
            raise ValueError(f'Expected one confined plugin directory for {name}')
        targets = [str(matches[0])]
    validate(root, Path(targets[0]) if targets else None)
    for script in ('test-path-resolution.sh',):
        path = root / 'scripts' / script
        if not path.is_file():
            raise ValueError(f'Target checkout lacks {path}')
        subprocess.run(['bash', str(path), *targets], cwd=root, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['add','remove','status','workflows','scan'])
    parser.add_argument('name', nargs='?')
    parser.add_argument('--root', '--marketplace-root')
    parser.add_argument('--description')
    parser.add_argument('--category', default='Productivity')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--regenerate', action='store_true', help='compatibility flag; removal always regenerates')
    parser.add_argument('--no-validate', action='store_true', help='skip scaffold validation only')
    args = parser.parse_args()
    try:
        root = resolve_root(args.root)
        if args.action == 'add':
            if not args.name: raise ValueError('add requires a plugin name')
            add(root, args.name, args.description or f'Project workflow for {args.name}.', args.category, args.no_validate)
        elif args.action == 'remove':
            if not args.name: raise ValueError('remove requires a plugin name')
            remove(root, args.name, args.force)
        elif args.action == 'workflows':
            workflows(root, args.name, args.force)
        elif args.action == 'scan':
            scan(root, args.name)
        else:
            catalog = load_catalog(root)
            found = catalog.plugins(root)
            print(json.dumps({'root': str(root), 'pluginCount': len(found), 'plugins': [
                {'name': name, 'version': data['version']} for name, (_, data) in sorted(found.items())],
                'staleCatalogs': catalog.generate(root, check=True)}, indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
