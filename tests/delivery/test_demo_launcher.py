import importlib.util
import json
from pathlib import Path
import socket
import sys

SPEC = importlib.util.spec_from_file_location('demo_launcher', Path(__file__).resolve().parents[2] / 'scripts/demo.py')
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


def test_preflight_is_read_only_and_rejects_occupied_port(tmp_path):
    target = tmp_path / 'new'
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        server.listen()
        errors = demo.inspect(target, server.getsockname()[1], 'simulation')
    assert any('Port unavailable' in e for e in errors)
    assert not target.exists()


def test_preflight_preserves_existing_evidence_and_requires_journal(tmp_path):
    errors = demo.inspect(tmp_path, 0, 'mqtt')
    assert any('already exists' in e for e in errors)
    assert any('existing external' in e for e in errors)
    assert any('Port must' in e for e in errors)


def test_start_passes_explicit_config_and_never_archives_secrets(tmp_path, monkeypatch):
    target = tmp_path / 'run'
    monkeypatch.setattr(sys, 'argv', ['demo.py', '--run-dir', str(target), '--start'])
    monkeypatch.setattr(demo, 'inspect', lambda *args: [])
    captured = {}
    def launch(command, cwd, env):
        captured.update(env)
        assert command == [sys.executable, '-m', 'edge']
        return 0
    monkeypatch.setattr(demo.subprocess, 'call', launch)
    assert demo.main() == 0
    text = (target / 'launch.json').read_text(encoding='utf8')
    record = json.loads(text)
    assert captured['AQUAGUARD_RUNTIME'] == 'simulation'
    assert captured['AQUAGUARD_DB'] == str(target / 'business.sqlite')
    assert len(captured['AQUAGUARD_C_TOKEN']) >= 24
    assert len(bytes.fromhex(captured['AQUAGUARD_C_CURSOR_KEY'])) >= 32
    assert captured['AQUAGUARD_C_TOKEN'] not in text
    assert captured['AQUAGUARD_C_CURSOR_KEY'] not in text
    assert record['b_acceptance'] == 'ON_HOLD'
    assert record['cloud_accepted'] is False
