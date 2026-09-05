#!/usr/bin/env python3
"""Offline end-to-end shell entrypoint tests. Never call a real cluster/VM."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/k8s-sidecar-testing/scripts'
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as log: log.write(json.dumps([pathlib.Path(sys.argv[0]).name, *args]) + '\n')
mode = os.environ.get('FAKE_MODE', '')
if pathlib.Path(sys.argv[0]).name == 'multipass':
    if mode == 'vm-down': print('daemon unavailable', file=sys.stderr); sys.exit(1)
    print('{"list": []}')
    sys.exit(0)
assert '--context=fixture' in args and '--namespace=sidecar-tests' in args, args
args = args[3:]
if args[:2] == ['get', 'namespace']: print('sidecar-tests'); sys.exit(0)
if args[:2] == ['apply', '--dry-run=client']:
    print(pathlib.Path(args[args.index('-f')+1]).read_text()); sys.exit(0)
if args[0] == 'apply':
    payload = sys.stdin.read()
    pathlib.Path(os.environ['APPLIED']).write_text(payload)
    sys.exit(0)
if args[0] in ['wait', 'delete']: sys.exit(0)
if args[0] == 'get':
    name = args[2]
    if '--ignore-not-found' in args:
        if mode in ['unowned', 'teardown-owned']:
            labels = {} if mode == 'unowned' else {'app.kubernetes.io/managed-by': 'k8s-sidecar-testing'}
            print(json.dumps({'metadata': {'labels': labels}}))
        sys.exit(0)
    ips = [{'ip': '10.42.0.2'}]
    if mode != 'no-ipv6': ips.append({'ip': 'fd00:42::2' if name == 'nat464-demo' else 'fd00:42::3'})
    print(json.dumps({'status': {'podIPs': ips}})); sys.exit(0)
if args[0] == 'exec':
    command = args[args.index('--')+1:]
    if command[:2] == ['sh', '-c']:
        if 'CURL_EXIT' in command[2]:
            print('CURL_EXIT=' + ('28' if mode == 'timeout-direct' else '0' if mode == 'direct-succeeds' else '7'))
            sys.exit(1 if mode == 'kubectl-direct-fails' else 0)
        if mode == 'ss-missing': print('ss missing', file=sys.stderr); sys.exit(127)
        print('State Recv-Q Send-Q Local Address:Port Peer Address:Port\nLISTEN 0 511 0.0.0.0:80 0.0.0.0:*')
        if mode == 'ipv6-listener': print('LISTEN 0 511 [::]:80 [::]:*')
        sys.exit(0)
    if '-w' in command:
        entries = pathlib.Path(os.environ['CALLS']).read_text().splitlines()
        samples = sum('time_connect' in entry for entry in entries)
        print('0.001 0.01 100')
        sys.exit(22 if mode == 'benchmark-partial' and samples == 1 else 7 if mode == 'benchmark-fail' else 0)
    url = command[-1]
    if '9464' in url:
        print('ok'); sys.exit(22 if mode == 'health-fail' else 0)
    if '8080' in url:
        print('nginx'); sys.exit(1 if mode == 'inbound-fail' else 0)
    print('ipv6-peer-ok'); sys.exit(0)
print('unhandled fake command: ' + repr(args), file=sys.stderr); sys.exit(99)
'''


class Scripts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sidecar-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for command in ('kubectl', 'multipass'):
            fake = self.bin / command
            fake.write_text(FAKE)
            fake.chmod(0o755)
        self.env = os.environ.copy()
        self.env.pop('KUBE_CONTEXT', None)
        self.env.pop('KUBE_NAMESPACE', None)
        self.env.update(PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        CALLS=str(self.root / 'calls.jsonl'), APPLIED=str(self.root / 'applied.json'))

    def run_script(self, name, *args, mode='', target=True):
        env = dict(self.env, FAKE_MODE=mode)
        params = ['--context', 'fixture', '--namespace', 'sidecar-tests'] if target else []
        return subprocess.run(['bash', str(SCRIPTS / (name + '.sh')), *params, *args],
                              cwd=self.root, env=env, text=True, capture_output=True, timeout=15)

    def calls(self):
        path = self.root / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def manifests(self):
        project = self.root / 'project with spaces'
        (project / 'deploy').mkdir(parents=True)
        for filename, name in [('example-pod.yaml', 'nat464-demo'), ('ipv6-peer-nginx.yaml', 'ipv6-peer')]:
            resource = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name},
                        'spec': {'containers': [{'name': 'nat464-sidecar', 'image': 'old', 'imagePullPolicy': 'Always'}]}}
            (project / 'deploy' / filename).write_text(json.dumps(resource))
        return project

    def test_requires_target_before_any_command(self):
        for args in [[], ['--context', 'fixture'], ['--namespace', 'sidecar-tests']]:
            result = self.run_script('validate-paths', *args, target=False)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_default_namespace_is_rejected(self):
        result = self.run_script('teardown', '--context', 'fixture', '--namespace', 'default', target=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_successful_validation_is_read_only_and_skips_external(self):
        result = self.run_script('validate-paths')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('5 passed, 0 failed', result.stdout)
        self.assertIn('SKIP: external', result.stdout)
        self.assertTrue(all(call[4] in {'get', 'exec'} for call in self.calls()))

    def test_failures_are_never_reported_as_success(self):
        for mode in ('health-fail', 'inbound-fail', 'timeout-direct', 'direct-succeeds',
                     'kubectl-direct-fails', 'ss-missing', 'ipv6-listener', 'no-ipv6'):
            with self.subTest(mode=mode):
                result = self.run_script('validate-paths', mode=mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn('5 passed, 0 failed', result.stdout)

    def test_missing_manifest_does_not_apply(self):
        result = self.run_script('deploy-test', '--project-dir', str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing project manifest', result.stderr)
        self.assertFalse(any(call[4] == 'apply' for call in self.calls()))

    def test_deploy_uses_project_paths_and_structural_image_patch(self):
        project = self.manifests()
        result = self.run_script('deploy-test', '--project-dir', str(project), '--local-image', 'demo:test')
        self.assertEqual(result.returncode, 0, result.stderr)
        applied = json.loads((self.root / 'applied.json').read_text())
        self.assertEqual(len(applied['items']), 2)
        sidecar = applied['items'][0]['spec']['containers'][0]
        self.assertEqual(sidecar['image'], 'demo:test')
        self.assertEqual(sidecar['imagePullPolicy'], 'Never')
        self.assertEqual(applied['items'][0]['metadata']['namespace'], 'sidecar-tests')
        self.assertFalse(any(call[4] == 'delete' for call in self.calls()))

    def test_deploy_propagates_validation_failure(self):
        result = self.run_script('deploy-test', '--project-dir', str(self.manifests()), mode='health-fail')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL: health endpoint', result.stdout)

    def test_unowned_resource_is_not_overwritten(self):
        result = self.run_script('deploy-test', '--project-dir', str(self.manifests()), mode='unowned')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'applied.json').exists())

    def test_rejects_cluster_scoped_and_wrong_namespace_manifests(self):
        project = self.manifests()
        path = project / 'deploy/ipv6-peer-nginx.yaml'
        original = json.loads(path.read_text())
        for change in [{'kind': 'Namespace'}, {'metadata': {'name': 'ipv6-peer', 'namespace': 'other'}}]:
            path.write_text(json.dumps(dict(original, **change)))
            result = self.run_script('deploy-test', '--project-dir', str(project))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.root / 'applied.json').exists())

    def test_benchmark_counts_failed_http_samples(self):
        result = self.run_script('benchmark', '--iterations', '2', mode='benchmark-partial')
        self.assertEqual(result.returncode, 1)
        self.assertIn('baseline: 1 successful, 1 failed', result.stdout)
        self.assertIn('sidecar: 2 successful, 0 failed', result.stdout)
        self.assertIn('p95=10.000', result.stdout)

    def test_all_failed_benchmark_exits_nonzero(self):
        result = self.run_script('benchmark', '--iterations', '1', mode='benchmark-fail')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0 successful, 1 failed', result.stdout)
        self.assertNotIn('payload rate', result.stdout)

    def test_invalid_benchmark_iterations_never_run_commands(self):
        for value in ('0', '-1', 'abc', '10001'):
            result = self.run_script('benchmark', '--iterations', value)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_teardown_preserves_unowned_resources(self):
        result = self.run_script('teardown', mode='unowned')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call[4] == 'delete' for call in self.calls()))

    def test_teardown_only_uses_known_names_and_ownership_selector(self):
        result = self.run_script('teardown', mode='teardown-owned')
        self.assertEqual(result.returncode, 0, result.stderr)
        deletes = [call for call in self.calls() if call[4] == 'delete']
        self.assertEqual(len(deletes), 4)
        for call in deletes:
            self.assertIn('--field-selector', call)
            self.assertIn('app.kubernetes.io/managed-by=k8s-sidecar-testing', call)
            self.assertNotIn('--all', call)

    def test_legacy_vm_teardown_is_rejected(self):
        result = self.run_script('teardown', '--vm')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_vm_daemon_error_never_launches(self):
        result = self.run_script('vm-setup', '--name', 'fixture', target=False, mode='vm-down')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.calls()[0][1], 'list')

    def load_helper(self):
        spec = importlib.util.spec_from_file_location('sidecar', SCRIPTS / 'sidecar.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_build_failure_never_imports_image(self):
        module = self.load_helper()
        (self.root / 'Dockerfile').write_text('FROM scratch\n')
        with mock.patch.object(module, 'require'), mock.patch.object(module, 'run', side_effect=module.Failure('build failed')) as run:
            with self.assertRaisesRegex(module.Failure, 'build failed'):
                module.build_image(SimpleNamespace(project_dir=str(self.root), image='demo:test'))
            self.assertEqual(run.call_count, 1)
            self.assertIn('build', run.call_args.args[0])

    def test_build_import_failure_is_not_success(self):
        module = self.load_helper()
        (self.root / 'Dockerfile').write_text('FROM scratch\n')
        def fake_run(args, **kwargs):
            if 'import' in args:
                self.assertIn('k8s.io', args)
                raise module.Failure('import failed')
            return subprocess.CompletedProcess(args, 0, '', '')
        with mock.patch.object(module, 'require'), mock.patch.object(module, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(module.Failure, 'import failed'):
                module.build_image(SimpleNamespace(project_dir=str(self.root), image='demo:test'))

    def test_setup_readiness_failure_is_not_success(self):
        module = self.load_helper()
        commands = []
        def fake_run(args, **kwargs):
            commands.append(args)
            if args[:3] == ['ip', '-j', 'addr']:
                return subprocess.CompletedProcess(args, 0, '[{"addr_info":[{"local":"10.0.0.2"},{"local":"fd00::1"}]}]', '')
            if 'wait' in args:
                raise module.Failure('readiness timed out')
            return subprocess.CompletedProcess(args, 0, '', '')
        with mock.patch.object(module, 'require'), mock.patch.object(module.shutil, 'which', return_value=None), mock.patch.object(module.Path, 'exists', return_value=False), mock.patch.object(module, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(module.Failure, 'readiness timed out'):
                module.k3s_setup(SimpleNamespace(version='v1.35.1+k3s1', node_ipv4='10.0.0.2', node_ipv6='fd00::1'))
        install = next(command for command in commands if command[0] == 'sh')
        self.assertIn('--write-kubeconfig-mode=600', install)
        self.assertFalse(any('apply' in command for command in commands))

    def test_bounded_runner_times_out(self):
        spec = importlib.util.spec_from_file_location('sidecar', SCRIPTS / 'sidecar.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(module.Failure, 'exceeded'):
            module.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.05)


if __name__ == '__main__':
    unittest.main()
