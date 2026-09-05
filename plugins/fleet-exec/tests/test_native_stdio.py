"""Launch the packaged native stdio server; initialize/list only, no tool calls."""
import json
import os
from pathlib import Path
import select
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_native_manifest_launcher_initializes_without_a_project_context():
    manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
    server = next(iter(json.loads((ROOT / manifest['mcpServers']).read_text()).values()))
    # Codex normalizes relative cwd against plugin_root (codex-mcp/plugin_config.rs).
    cwd = ROOT / server['cwd']
    assert cwd.resolve() == ROOT.resolve()
    assert all('${' not in value for value in server['args'])
    env = dict(os.environ, **server.get('env', {}))
    env.pop('BRAVE_API_KEY', None)
    proc = subprocess.Popen([server['command'], *server['args']], cwd=cwd, env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    try:
        def exchange(payload):
            proc.stdin.write(json.dumps(payload) + '\n')
            proc.stdin.flush()
            assert select.select([proc.stdout], [], [], 15)[0], 'stdio response deadline exceeded'
            return json.loads(proc.stdout.readline())
        response = exchange({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                             'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                                        'clientInfo': {'name': 'offline-regression', 'version': '1'}}})
        assert response['id'] == 1 and 'result' in response
        proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
        proc.stdin.flush()
        response = exchange({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
        assert response['id'] == 2 and response['result']['tools']
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
        for stream in [proc.stdin, proc.stdout, proc.stderr]: stream.close()
