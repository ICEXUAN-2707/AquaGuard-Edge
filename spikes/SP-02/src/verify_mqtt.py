"""Real local Broker scenarios; isolated port and owned subprocesses only."""
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core import sample


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError('scenario readiness timeout')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', required=True, type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--port', type=int, default=18884)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    # Refuse occupied port rather than accidentally testing someone else's Broker.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
    config = args.directory/'broker.conf'
    config.write_text(f'listener {args.port} 127.0.0.1\nallow_anonymous true\npersistence false\n')
    cli = Path(__file__).with_name('cli.py')
    results = []
    processes = []
    logs = []

    def start_broker(label):
        log = (args.directory/f'broker-{label}.log').open('w')
        logs.append(log)
        process = subprocess.Popen([str(args.broker), '-c', str(config), '-v'], stdout=log, stderr=log)
        processes.append(process)
        def listening():
            if process.poll() is not None:
                raise RuntimeError('owned Broker exited')
            with socket.socket() as connection:
                return connection.connect_ex(('127.0.0.1', args.port)) == 0
        wait_for(listening)
        return process

    def scenario(label, rows, expected, directory=None):
        directory = directory or args.directory/label
        directory.mkdir(exist_ok=True)
        (directory/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
        logpath = directory/f'{label}-subscriber.log'
        log = logpath.open('w')
        logs.append(log)
        command = [sys.executable, str(cli)]
        subscriber = subprocess.Popen(command+['subscribe','--directory',str(directory),'--port',str(args.port),'--seconds','3'], stdout=log, stderr=log)
        processes.append(subscriber)
        wait_for(lambda: 'READY' in logpath.read_text() if subscriber.poll() is None else False)
        published = subprocess.run(command+['publish','--directory',str(directory),'--port',str(args.port)], capture_output=True, text=True, timeout=15)
        (directory/f'{label}-publisher.log').write_text(published.stdout+published.stderr)
        if published.returncode:
            raise RuntimeError('publisher failed')
        subscriber.wait(timeout=10)
        if subscriber.returncode != (1 if 'invalid' in expected else 0):
            raise RuntimeError('subscriber failed')
        records = [json.loads(line) for line in (directory/'received.jsonl').read_text().splitlines()]
        # A reused directory contains previous subscriber runs as well.
        actual = [r['classification'] for r in records][-len(rows):]
        result = dict(scenario=label, expected=expected, actual=actual, status='PASS' if actual == expected else 'FAIL')
        results.append(result)
        if result['status'] != 'PASS':
            raise AssertionError(result)
        return directory

    try:
        broker = start_broker('first')
        shared = scenario('duplicate-order', [sample(3),sample(1),sample(3)], ['new','out_of_order','duplicate'])
        conflict = sample(5)
        conflict['value']['wet'] = True
        malformed = sample(6)
        malformed['prototype_only'] = True
        scenario('conflict-and-invalid', [sample(5), conflict, malformed, sample(7)],
                 ['new','conflict','invalid','new'])
        scenario('subscriber-and-publisher-restart', [sample(3),sample(0,boot='boot-2')], ['duplicate','new'], shared)
        broker.terminate()
        broker.wait(timeout=5)
        broker = start_broker('restarted')
        scenario('broker-restart', [sample(3),sample(1,boot='boot-2')], ['duplicate','new'], shared)
        # Keep this subscriber process alive across a real Broker interruption.
        live = args.directory/'live-reconnect'
        live.mkdir()
        log = (live/'subscriber.log').open('w')
        logs.append(log)
        subscriber = subprocess.Popen([sys.executable,str(cli),'subscribe','--directory',str(live),
                                       '--port',str(args.port),'--seconds','15'],stdout=log,stderr=log)
        processes.append(subscriber)
        def events():
            path = live/'subscribe-connections.jsonl'
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        wait_for(lambda: any(e['event']=='subscribed' for e in events()))
        broker.terminate()
        broker.wait(timeout=5)
        wait_for(lambda: any(e['event']=='disconnected' for e in events()))
        broker = start_broker('live-recovery')
        wait_for(lambda: sum(e['event']=='subscribed' for e in events()) >= 2)
        (live/'manifest.jsonl').write_text(json.dumps(sample(99))+'\n')
        subprocess.run([sys.executable,str(cli),'publish','--directory',str(live),'--port',str(args.port)],
                       check=True,capture_output=True,timeout=10)
        subscriber.wait(timeout=20)
        records = [json.loads(line) for line in (live/'received.jsonl').read_text().splitlines()]
        timeline = events()
        disconnected = next(e['monotonic'] for e in timeline if e['event']=='disconnected')
        recovered = next(e['monotonic'] for e in timeline if e['event']=='subscribed' and e['monotonic']>disconnected)
        passed = subscriber.returncode == 0 and len(records)==1 and records[0]['classification']=='new'
        results.append(dict(scenario='live-subscriber-reconnect',status='PASS' if passed else 'FAIL',
                            recovery_seconds=recovered-disconnected, received=len(records)))
        if not passed:
            raise AssertionError('live reconnect failed')
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        for log in logs:
            log.close()
        (args.directory/'summary.json').write_text(json.dumps(dict(results=results, complete=len(results)==5), indent=2))
    print(json.dumps(results))


if __name__ == '__main__':
    main()
