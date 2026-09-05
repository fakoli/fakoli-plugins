#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6,<7", "jsonschema>=4.23,<5"]
# ///
"""Validate shipped manifests, actual skill entrypoints and catalog consistency."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

import jsonschema
import yaml

from catalog import ROOT, read_json, build_outputs
import importlib.util

_creator_path = ROOT / "tools/plugin-creator/scripts/validate_plugin.py"
_spec = importlib.util.spec_from_file_location("codex_preflight", _creator_path)
_creator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_creator)

NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def validate_plugin(path, schemas=ROOT / 'schemas'):
    errors = _creator.validate_plugin(path)
    manifests = {}
    for host, schema in (('claude', 'plugin.schema.json'), ('codex', 'codex-plugin.schema.json')):
        manifest_path = path / f'.{host}-plugin/plugin.json'
        try:
            data = read_json(manifest_path)
            if host == 'claude':
                validator = jsonschema.Draft202012Validator(read_json(schemas / schema))
                for error in validator.iter_errors(data):
                    errors.append(f'{manifest_path}: {error.json_path}: {error.message}')
            if not isinstance(data, dict):
                continue
            manifests[host] = data
            if data.get('name') != path.name:
                errors.append(f'{manifest_path}: name must match directory {path.name}')
            for key in ('skills', 'commands', 'agents', 'hooks', 'mcpServers', 'apps', 'outputStyles', 'lspServers'):
                value = data.get(key)
                for source in value if isinstance(value, list) else [value]:
                    if not isinstance(source, str):
                        continue
                    target = (path / source).resolve()
                    if not source.startswith('./') or not target.is_relative_to(path.resolve()) or not target.exists():
                        errors.append(f'{manifest_path}: {key} path must exist inside plugin: {source}')
        except (OSError, ValueError) as error:
            errors.append(f'{manifest_path}: {error}')
    if len(manifests) == 2:
        for field in ('name', 'version'):
            if manifests['claude'].get(field) != manifests['codex'].get(field):
                errors.append(f'{path}: {field} differs between host manifests')
    skills = sorted((path / 'skills').glob('*/SKILL.md'))
    for skill in skills:
        text = skill.read_text(encoding='utf-8')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
        try:
            data = yaml.safe_load(match.group(1)) if match else None
            if not isinstance(data, dict):
                raise ValueError('missing YAML frontmatter mapping')
            if not isinstance(data.get('name'), str) or not NAME.fullmatch(data['name']) or len(data['name']) > 64:
                errors.append(f'{skill}: invalid skill name')
            elif data['name'] != skill.parent.name:
                errors.append(f'{skill}: name must match skill directory')
            if not isinstance(data.get('description'), str) or not data['description'].strip() or len(data['description']) > 1024:
                errors.append(f'{skill}: description must contain 1–1024 characters')
            if 'user_invocable' in data:
                errors.append(f'{skill}: unsupported user_invocable; omit or use host-supported metadata')
        except (yaml.YAMLError, ValueError) as error:
            errors.append(f'{skill}: {error}')
        for link in re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text):
            if ':' in link or link.startswith('#') or '<' in link:
                continue
            target = (skill.parent / unquote(link.split('#', 1)[0])).resolve()
            if not target.exists():
                errors.append(f'{skill}: broken or escaping resource link {link}')
    return errors


def validate_repository(root, check_catalog=True):
    errors = []
    for folder in ('plugins', 'external_plugins'):
        for path in sorted((root / folder).glob('*')):
            if path.is_dir():
                errors.extend(validate_plugin(path, root / 'schemas'))
    try:
        for catalog, native in (('.claude-plugin/marketplace.json', False), ('.agents/plugins/marketplace.json', True)):
            data = read_json(root / catalog)
            schema = 'codex-marketplace.schema.json' if native else 'marketplace.schema.json'
            for error in jsonschema.Draft202012Validator(read_json(root / 'schemas' / schema)).iter_errors(data):
                errors.append(f'{catalog}: {error.json_path}: {error.message}')
            seen = set()
            for entry in data.get('plugins', []):
                name = entry.get('name')
                if name in seen:
                    errors.append(f'{catalog}: duplicate entry {name}')
                seen.add(name)
                source = entry.get('source', {}).get('path') if native else entry.get('source')
                if not isinstance(source, str) or not source.startswith('./'):
                    errors.append(f'{catalog}: invalid local source {source}')
                    continue
                target = (root / source).resolve()
                if not target.is_relative_to(root.resolve()) or not target.is_dir():
                    errors.append(f'{catalog}: missing or escaping plugin {source}')
                elif target.name != name:
                    errors.append(f'{catalog}: source/name mismatch {name}')
        if check_catalog and not errors:
            for relative, expected in build_outputs(root).items():
                if not (root / relative).exists() or read_json(root / relative) != expected:
                    errors.append(f'{relative}: stale; run scripts/generate-index.sh')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f'catalog validation: {error}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plugin', nargs='?', type=Path)
    parser.add_argument('--root', default=ROOT, type=Path)
    parser.add_argument('--no-catalog-check', action='store_true')
    args = parser.parse_args()
    errors = validate_plugin(args.plugin.resolve(), args.root / 'schemas') if args.plugin else validate_repository(args.root.resolve(), not args.no_catalog_check)
    if errors:
        print('\n'.join('ERROR: ' + error for error in errors), file=sys.stderr)
        return 1
    print('Validation passed: manifests, skills, resource links' + ('' if args.plugin else ', marketplaces and registry.'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
