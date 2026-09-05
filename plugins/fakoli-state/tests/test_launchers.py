"""The installed entrypoints must preserve project scope and startup failures."""
import json
import os
from pathlib import Path
import subprocess
import asyncio
import shutil

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fakoli_state.mcp_server import mcp

PLUGIN = Path(__file__).resolve().parents[1]


def test_cli_and_mcp_use_one_locked_external_environment(tmp_path):
    shim = tmp_path / 'shim'
    shim.mkdir()
    uv = shim / 'uv'
    uv.write_text('#!/usr/bin/env python3\nimport json, os, sys\nprint(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd(),"env":os.environ["UV_PROJECT_ENVIRONMENT"]}))\nsys.exit(17)\n')
    uv.chmod(0o755)
    project = tmp_path / 'project with spaces'
    project.mkdir()
    env = dict(os.environ, PATH=str(shim) + os.pathsep + os.environ['PATH'], FAKOLI_STATE_ENVIRONMENT=str(tmp_path / 'runtime cache'), FAKOLI_STATE_EXTRAS='')
    for launcher, module in [('fakoli-state', 'cli'), ('fakoli-state-mcp', 'mcp_server')]:
        result = subprocess.run(['bash', str(PLUGIN / 'bin' / launcher), '--help'], cwd=project, env=env, capture_output=True, text=True)
        assert result.returncode == 17
        data = json.loads(result.stdout)
        assert data['cwd'] == str(project.resolve())
        assert data['env'] == str(tmp_path / 'runtime cache')
        assert data['args'] == ['run', '--quiet', '--locked', '--no-dev', '--project', str(PLUGIN / 'bin'), 'python', '-m', 'fakoli_state.' + module, '--help']
        assert not list(project.iterdir())


def test_native_mcp_routes_to_explicit_project_and_rejects_cache_default(tmp_path, monkeypatch):
    installed = tmp_path / 'installed'
    (installed / '.codex-plugin').mkdir(parents=True)
    (installed / '.codex-plugin/plugin.json').write_text('{}')
    project = tmp_path / 'actual-project'
    project.mkdir()
    monkeypatch.chdir(installed)

    async def exercise():
        async with Client(mcp) as client:
            await client.call_tool('init_project', {'name': 'Actual Project', 'cwd': str(project)})
            result = await client.call_tool('get_project_summary', {'cwd': str(project)})
            assert result.structured_content['project_name'] == 'Actual Project'
            result = await client.call_tool('list_tasks', {'cwd': str(project)})
            assert result.data == []
            with pytest.raises(ToolError, match='Pass cwd'):
                await client.call_tool('get_project_summary', {})
            tools = await client.list_tools()
            assert all('cwd' in tool.inputSchema['properties'] for tool in tools)

    asyncio.run(exercise())
    assert not (installed / '.fakoli-state').exists()


def test_selected_provider_extras_work_in_the_actual_launcher_environment(tmp_path):
    assert shutil.which('uv'), 'uv is required for the packaged launcher'
    runtime = tmp_path / 'provider-runtime'
    env = dict(os.environ, FAKOLI_STATE_ENVIRONMENT=str(runtime), FAKOLI_STATE_EXTRAS='all-providers')
    result = subprocess.run(['bash', str(PLUGIN / 'bin/fakoli-state'), '--version'], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    result = subprocess.run([str(python), '-c', 'import openai, boto3; print("provider SDKs import")'],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'provider SDKs import' in result.stdout
    assert not (tmp_path / '.fakoli-state').exists()


def test_unknown_provider_extra_fails_before_uv(tmp_path):
    env = dict(os.environ, FAKOLI_STATE_ENVIRONMENT=str(tmp_path / 'unused'), FAKOLI_STATE_EXTRAS='unknown')
    result = subprocess.run(['bash', str(PLUGIN / 'bin/fakoli-state'), '--version'], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert 'FAKOLI_STATE_EXTRAS' in result.stderr
    assert not (tmp_path / 'unused').exists()
