import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import catalog
from validate import validate_plugin, validate_repository

spec = importlib.util.spec_from_file_location('manager', ROOT / 'plugins/marketplace-manager/skills/marketplace-manager/scripts/manage.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='marketplace test ')
        self.root = Path(self.temp.name).resolve()
        for folder in ('scripts', 'schemas', 'templates', 'tools'):
            shutil.copytree(ROOT / folder, self.root / folder)
        (self.root / '.claude-plugin').mkdir()
        catalog.atomic_json(self.root / catalog.CLAUDE_CATALOG, {'name':'fixture','owner':{'name':'Fixture'},'plugins':[]})
        (self.root / 'README.md').write_text('| Plugin | Category | Description |\n<!-- plugin-list:end -->\n')
        catalog.generate(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, name='example'):
        manager.add(self.root, name, 'Test a concrete local workflow.', 'Productivity', no_validate=True)

    def test_scaffold_generates_both_valid_hosts_and_removal_cleans_catalogs(self):
        self.add()
        self.assertEqual(validate_repository(self.root), [])
        self.assertIn('[example]', (self.root / 'README.md').read_text())
        manager.remove(self.root, 'example', force=True)
        self.assertFalse((self.root / 'plugins/example').exists())
        self.assertEqual(catalog.read_json(self.root / catalog.CODEX_CATALOG)['plugins'], [])
        self.assertNotIn('[example]', (self.root / 'README.md').read_text())

    def test_generator_preserves_order_policy_metadata_and_is_idempotent(self):
        self.add('z-first'); self.add('a-second')
        file = self.root / catalog.CODEX_CATALOG
        data = catalog.read_json(file)
        data['plugins'][0]['policy']['products'] = ['codex']
        data['plugins'][0]['policy']['installation'] = 'NOT_AVAILABLE'
        data['plugins'][0]['customMetadata'] = {'keep':True}
        catalog.atomic_json(file, data)
        catalog.generate(self.root)
        self.assertEqual(catalog.read_json(file), data)
        self.assertEqual([p['name'] for p in data['plugins']], ['z-first','a-second'])
        before = file.stat().st_mtime_ns
        self.assertEqual(catalog.generate(self.root), [])
        self.assertEqual(file.stat().st_mtime_ns, before)

    def test_remote_catalog_is_rejected_without_rewrite(self):
        file = self.root / catalog.CODEX_CATALOG
        data = catalog.read_json(file)
        data['plugins'] = [{'name':'remote','source':{'source':'git','url':'https://example.invalid/repo'}}]
        catalog.atomic_json(file, data)
        before = file.read_bytes()
        with self.assertRaisesRegex(ValueError, 'local Codex'):
            catalog.generate(self.root)
        self.assertEqual(before, file.read_bytes())

    def test_bad_names_and_symlink_destinations_never_mutate(self):
        self.add()
        for name in ['../example', '..', '.', '', 'bad--name', '/tmp', '-name', 'a'*65]:
            with self.assertRaises(ValueError): manager.remove(self.root, name, force=True)
        (self.root / 'plugins/linked').symlink_to(self.root / 'plugins/example', target_is_directory=True)
        with self.assertRaises(ValueError): manager.remove(self.root, 'linked', force=True)
        self.assertTrue((self.root / 'plugins/example').exists())
        with self.assertRaises(ValueError): manager.remove(self.root, 'example')

    def test_failed_validation_rolls_back_scaffold_and_catalogs(self):
        before = {p:(self.root / p).read_bytes() for p in manager.SHARED if (self.root / p).exists()}
        with patch.object(manager, 'validate', side_effect=subprocess.CalledProcessError(1,'validator')):
            with self.assertRaises(subprocess.CalledProcessError):
                manager.add(self.root, 'broken', 'A test description.', 'Productivity')
        self.assertFalse((self.root / 'plugins/broken').exists())
        self.assertFalse((self.root / '.marketplace-manager.lock').exists())
        for p, content in before.items(): self.assertEqual((self.root / p).read_bytes(), content)

    def test_failed_removal_restores_original_plugin(self):
        self.add()
        before = (self.root / 'plugins/example/skills/example/SKILL.md').read_bytes()
        fake = manager.load_catalog(self.root)
        with patch.object(fake, 'generate', side_effect=ValueError('bad catalog')), patch.object(manager, 'load_catalog', return_value=fake):
            with self.assertRaisesRegex(ValueError, 'bad catalog'): manager.remove(self.root, 'example', force=True)
        self.assertEqual((self.root / 'plugins/example/skills/example/SKILL.md').read_bytes(), before)
        self.assertEqual(validate_repository(self.root), [])

    def test_installed_helper_targets_explicit_checkout_from_unrelated_cwd(self):
        result = subprocess.run([sys.executable, str(Path(manager.__file__)), 'status', '--root', str(self.root)], cwd='/', capture_output=True, text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['root'],str(self.root))

    def test_validator_rejects_bad_skill_yaml_links_types_and_stale_versions(self):
        self.add()
        path = self.root / 'plugins/example'
        skill = path / 'skills/example/SKILL.md'
        skill.write_text('---\nname: example\ndescription: [bad]\n---\n[missing](references/missing.md)\n')
        errors = validate_plugin(path, self.root / 'schemas')
        self.assertTrue(any('description' in e for e in errors))
        self.assertTrue(any('resource link' in e for e in errors))
        file = path / '.claude-plugin/plugin.json'
        data = catalog.read_json(file);data['version']='2.0.0';data['keywords']=[3];catalog.atomic_json(file,data)
        errors = validate_plugin(path, self.root / 'schemas')
        self.assertTrue(any('version differs' in e for e in errors))
        self.assertTrue(any('keywords' in e for e in errors))

    def test_marketplace_lock_prevents_second_operation(self):
        with manager.transaction(self.root):
            with self.assertRaisesRegex(ValueError, 'Another operation'):
                self.add()
        self.assertFalse((self.root / 'plugins/example').exists())

    def test_curated_category_and_readme_bold_links_survive_management(self):
        self.add()
        entry = catalog.read_json(self.root / catalog.CLAUDE_CATALOG)['plugins'][0]
        self.assertEqual(entry['category'], 'productivity')
        readme = self.root / 'README.md'
        readme.write_text(readme.read_text().replace('[example]', '[**example**]'))
        manager.remove(self.root, 'example', force=True)
        self.assertNotIn('plugins/example', readme.read_text())

    def test_check_reports_drift_without_writing_any_artifact(self):
        self.add()
        file = self.root / 'registry/index.json'
        data = catalog.read_json(file)
        data['pluginCount'] = 777
        catalog.atomic_json(file, data)
        before = {p: ((self.root / p).read_bytes(), (self.root / p).stat().st_mtime_ns)
                  for p in manager.SHARED if (self.root / p).exists()}
        self.assertIn('registry/index.json', catalog.generate(self.root, check=True))
        for path, snapshot in before.items():
            self.assertEqual(((self.root / path).read_bytes(), (self.root / path).stat().st_mtime_ns), snapshot)

    def test_scan_uses_selected_checkout_and_propagates_failure(self):
        self.add()
        with patch.object(manager.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'scan')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                manager.scan(self.root, 'example')
        self.assertEqual(run.call_args.kwargs['cwd'], self.root)
        self.assertEqual(run.call_args.args[0][-1], str(self.root / 'plugins/example'))

    def test_manager_invokes_native_validation_for_scaffolds(self):
        self.add()
        with patch.object(manager.subprocess, 'run') as run:
            manager.validate(self.root, self.root / 'plugins/example')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[-1], ['uv', 'run', '--script', str(self.root / 'scripts/validate.py'), str(self.root / 'plugins/example')])

    def test_workflow_install_rejects_symlink_escape_before_writing(self):
        github = self.root / '.github'
        github.mkdir()
        outside = self.root.parent / (self.root.name + '-outside')
        outside.mkdir()
        try:
            (github / 'workflows').symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'real directory'):
                manager.workflows(self.root, None, force=True)
            self.assertEqual(list(outside.iterdir()), [])
            (github / 'workflows').unlink()
            (github / 'workflows').mkdir()
            victim = outside / 'victim.yml'
            victim.write_text('original')
            (github / 'workflows/validate.yml').symlink_to(victim)
            with self.assertRaisesRegex(ValueError, 'confined regular file'):
                manager.workflows(self.root, None, force=True)
            self.assertEqual(victim.read_text(), 'original')
            self.assertFalse((github / 'workflows/pr-check.yml').exists())
        finally:
            shutil.rmtree(outside)

    def test_invalid_semver_and_duplicate_catalog_are_reported(self):
        self.add()
        file=self.root / 'plugins/example/.claude-plugin/plugin.json'
        data=catalog.read_json(file);data['version']='1.0.0-01';catalog.atomic_json(file,data)
        self.assertTrue(any('version' in e for e in validate_plugin(file.parent.parent,self.root/'schemas')))
        file=self.root/catalog.CLAUDE_CATALOG;data=catalog.read_json(file);data['plugins']*=2;catalog.atomic_json(file,data)
        self.assertTrue(any('duplicate' in e for e in validate_repository(self.root)))


if __name__ == '__main__':
    unittest.main()
