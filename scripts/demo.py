"""Local demo preflight/launcher; no B evaluation, cloud provisioning or broker ownership."""
import argparse
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def inspect(run_dir, port, mode, journal=None):
    problems = []
    for package in ('fastapi', 'uvicorn', 'pydantic', 'paho-mqtt'):
        try:
            version(package)
        except PackageNotFoundError:
            problems.append(f'Missing dependency: {package}; install requirements-app.lock.txt')
    for relative in ('web/dist/c.html', 'spikes/C-business/run.py', 'spikes/SP-03/src', 'spikes/SP-03-features/src', 'spikes/SP-04/src'):
        if not (ROOT / relative).exists():
            problems.append(f'Missing repository/build asset: {relative}')
    if run_dir.exists():
        problems.append('Run directory already exists; choose a new path to preserve evidence')
    if not 1 <= port <= 65535:
        problems.append('Port must be between 1 and 65535')
    else:
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
        except OSError:
            problems.append('Port unavailable; choose another port; do not stop unrelated services')
    if mode == 'mqtt' and (journal is None or not journal.is_file()):
        problems.append('MQTT mode requires an existing external SP-02 journal')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8030)
    parser.add_argument('--mode', choices=('simulation', 'mqtt'), default='simulation')
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--start', action='store_true', help='without this flag, check only; no files or services created')
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    journal = args.journal.resolve() if args.journal else None
    problems = inspect(run_dir, args.port, args.mode, journal)
    print(json.dumps(dict(status='FAIL' if problems else 'PASS', mode=args.mode,
                         source='simulation', cloud_accepted=False, b_acceptance='ON_HOLD',
                         run_dir=str(run_dir), problems=problems), ensure_ascii=False))
    if problems:
        return 2
    if not args.start:
        return 0
    run_dir.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(AQUAGUARD_RUNTIME=args.mode, AQUAGUARD_DEVICE_ID='demo01',
               AQUAGUARD_HOST='127.0.0.1', AQUAGUARD_PORT=str(args.port),
               AQUAGUARD_DB=str(run_dir / 'business.sqlite'),
               AQUAGUARD_C_TOKEN=secrets.token_hex(24), AQUAGUARD_C_CURSOR_KEY=secrets.token_hex(32))
    if journal:
        env['AQUAGUARD_MQTT_JOURNAL'] = str(journal)
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, capture_output=True, text=True)
    (run_dir / 'launch.json').write_text(json.dumps(dict(
        revision=revision.stdout.strip() if revision.returncode == 0 else 'unknown',
        tracked_changes=bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        mode=args.mode, source='simulation', port=args.port,
        cloud_accepted=False, b_acceptance='ON_HOLD'), indent=2), encoding='utf8')
    print(f'Open http://127.0.0.1:{args.port}/c.html', flush=True)
    print('Local access token (do not record/share): ' + env['AQUAGUARD_C_TOKEN'], flush=True)
    print('Ctrl+C stops this foreground service. MQTT broker/subscriber remain externally owned.', flush=True)
    try:
        return subprocess.call([sys.executable, '-m', 'edge'], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
