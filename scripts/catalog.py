#!/usr/bin/env python3
"""Deterministic local catalog generation. No installation or network operations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_CATALOG = Path('.claude-plugin/marketplace.json')
CODEX_CATALOG = Path('.agents/plugins/marketplace.json')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, value):
    """Leave unchanged files untouched and replace changed files atomically."""
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(data)
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def plugins(root):
    found = {}
    for folder in ('plugins', 'external_plugins'):
        for path in sorted((root / folder).glob('*/.claude-plugin/plugin.json')):
            manifest = read_json(path)
            name = manifest['name']
            plugin_root = path.parent.parent
            if name in found or name != plugin_root.name:
                raise ValueError(f'duplicate or mismatched plugin name: {name}')
            if not plugin_root.resolve().is_relative_to(root.resolve()):
                raise ValueError(f'plugin escapes repository: {name}')
            found[name] = (plugin_root, manifest)
    return found


def build_outputs(root):
    found = plugins(root)
    old_claude = read_json(root / CLAUDE_CATALOG)
    old_entries = old_claude.get('plugins', [])
    names = [p['name'] for p in old_entries]
    if len(names) != len(set(names)):
        raise ValueError('duplicate marketplace entries')
    # Only local source entries are managed here. Never drop a remote catalog entry.
    if any(not isinstance(p.get('source'), str) or not p['source'].startswith('./') for p in old_entries):
        raise ValueError('this catalog generator manages local sources only; remote entries require explicit handling')
    for entry in old_entries:
        name = entry['name']
        if name not in found or (root / entry['source']).resolve() != found[name][0].resolve():
            raise ValueError(f'Claude source is missing or mismatched for {name}; fix the source or use the removal helper')
    order = [name for name in names if name in found]
    order += sorted(set(found) - set(order))
    previous = {p['name']: p for p in old_entries}
    codex_path = root / CODEX_CATALOG
    codex = read_json(codex_path) if codex_path.exists() else {
        'name': old_claude['name'], 'interface': {'displayName': 'Fakoli Plugins'}, 'plugins': []}
    old_codex = {p['name']: p for p in codex.get('plugins', [])}
    if len(old_codex) != len(codex.get('plugins', [])):
        raise ValueError('duplicate Codex marketplace entries')
    if any(p.get('source', {}).get('source') != 'local' for p in old_codex.values()):
        raise ValueError('this catalog generator manages local Codex sources only')
    for name, entry in old_codex.items():
        if name not in found or (root / entry['source']['path']).resolve() != found[name][0].resolve():
            raise ValueError(f'Codex source is missing or mismatched for {name}; fix the source or use the removal helper')
    claude_entries, codex_entries, index = [], [], []
    for name in order:
        path, manifest = found[name]
        source = './' + path.relative_to(root).as_posix()
        native = read_json(path / '.codex-plugin/plugin.json')
        category = native.get('interface', {}).get('category', 'Productivity')
        entry = dict(previous.get(name, {}))
        entry.update(name=name, source=source, version=manifest['version'])
        entry.setdefault('description', manifest['description'])
        entry.setdefault('category', 'development')
        claude_entries.append(entry)
        native_entry = dict(old_codex.get(name, {}))
        native_entry.update(name=name, source={'source': 'local', 'path': source})
        native_entry.setdefault('policy', {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'})
        native_entry.setdefault('category', category)
        codex_entries.append(native_entry)
        index.append({**{k: manifest[k] for k in ('name', 'version', 'description', 'author', 'repository', 'license', 'keywords', 'homepage') if k in manifest},
                      'path': source[2:], 'category': entry['category'], 'description': entry['description']})
    # Preserve Codex render order independently of the Claude marketplace order.
    codex_by_name = {p['name']: p for p in codex_entries}
    codex_order = [name for name in old_codex if name in codex_by_name]
    codex_order += [name for name in order if name not in codex_order]
    codex['plugins'] = [codex_by_name[name] for name in codex_order]
    old_claude['plugins'] = claude_entries
    categories = []
    for category in sorted({p['category'] for p in index}):
        entries = [{k: p[k] for k in ('name', 'version', 'description', 'path')}
                   for p in index if p['category'] == category]
        entries.sort(key=lambda p: p['name'])
        categories.append({'category': category, 'count': len(entries), 'plugins': entries})
    index.sort(key=lambda p: p['name'])
    tags = {}
    for plugin in index:
        for tag in plugin.get('keywords', []):
            tags.setdefault(tag, []).append(plugin['name'])
    used_categories = {p['category'] for p in index}
    definitions = old_claude.get('categories', [])
    known = {c['id']: c for c in definitions}
    for category in used_categories:
        known.setdefault(category, {'id': category, 'name': category.replace('-', ' ').title()})
    old_claude['categories'] = [c for c in known.values() if c['id'] in used_categories]
    now = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    previous_index = root / 'registry/index.json'
    old_index = {p['name']: p for p in read_json(previous_index).get('plugins', [])} if previous_index.exists() else {}
    for plugin in index:
        old = old_index.get(plugin['name'], {})
        plugin['indexedAt'] = old.get('indexedAt', now) if without_timestamps(old) == plugin else now
    outputs = {
        CLAUDE_CATALOG: old_claude, CODEX_CATALOG: codex,
        Path('registry/index.json'): {'$schema': '../schemas/index.schema.json', 'version': '1.0.0', 'generatedAt': now, 'pluginCount': len(index), 'plugins': index},
        Path('registry/categories.json'): {'generatedAt': now, 'categories': categories},
        Path('registry/tags.json'): {'generatedAt': now, 'totalTags': len(tags), 'tags': [
            {'tag': tag, 'count': len(names), 'plugins': sorted(names)}
            for tag, names in sorted(tags.items(), key=lambda p: (-len(p[1]), p[0]))]},
    }
    # Preserve byte content and timestamps when semantics are unchanged.
    for relative, data in outputs.items():
        if (root / relative).exists():
            previous_data = read_json(root / relative)
            if without_timestamps(previous_data) == without_timestamps(data):
                outputs[relative] = previous_data
    return outputs


def without_timestamps(value):
    if isinstance(value, dict):
        return {k: without_timestamps(v) for k, v in value.items() if k not in ('generatedAt', 'indexedAt')}
    if isinstance(value, list):
        return [without_timestamps(v) for v in value]
    return value


def generate(root, check=False):
    outputs = build_outputs(root)
    changed = []
    for relative, data in outputs.items():
        path = root / relative
        if not path.exists() or read_json(path) != data:
            changed.append(relative.as_posix())
    if not check:
        for relative, data in outputs.items():
            atomic_json(root / relative, data)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true', help='fail on stale catalogs without writing')
    args = parser.parse_args()
    try:
        changed = generate(args.root.resolve(), args.check)
        if args.check and changed:
            parser.exit(1, 'Stale catalogs: ' + ', '.join(changed) + '\nRun scripts/generate-index.sh\n')
        print('Catalogs current.' if not changed else 'Updated: ' + ', '.join(changed))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Catalog error: {error}\n')


if __name__ == '__main__':
    main()
