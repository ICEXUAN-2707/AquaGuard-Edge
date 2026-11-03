"""Inject process death after SQLite commit and before MQTT ACK."""
import argparse
import json
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

from verify_mqtt import wait_for


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', required=True)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    run = args.directory
    run.mkdir(parents=True, exist_ok=False)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',18886))
    config = run/'broker.conf'
    config.write_text('listener 18886 127.0.0.1\nallow_anonymous true\npersistence false\n')
    cli = str(Path(__file__).with_name('cli.py'))
    command = [sys.executable,cli]
    processes = []
    with (run/'broker.log').open('w') as brokerlog, (run/'first.log').open('w') as firstlog:
        try:
            broker = subprocess.Popen([args.broker,'-c',str(config),'-v'],stdout=brokerlog,stderr=brokerlog)
            processes.append(broker)
            def listening():
                with socket.socket() as connection:
                    return connection.connect_ex(('127.0.0.1',18886)) == 0
            wait_for(listening)
            common = ['--directory',str(run),'--port','18886']
            subprocess.run(command+['generate',*common,'--count','1'],check=True)
            first = subprocess.Popen(command+['subscribe',*common,'--persistent-session','--crash-after-commit'],stdout=firstlog,stderr=firstlog)
            processes.append(first)
            wait_for(lambda: 'READY' in (run/'first.log').read_text())
            subprocess.run(command+['publish',*common],check=True,capture_output=True,timeout=10)
            assert first.wait(timeout=10) == 73, 'fault injection exit code mismatch'
            second = subprocess.run(command+['subscribe',*common,'--persistent-session','--seconds','3'],capture_output=True,text=True,timeout=15)
            (run/'second.log').write_text(second.stdout+second.stderr)
            assert second.returncode == 0
            with sqlite3.connect(run/'journal.sqlite') as db:
                classifications = [r[0] for r in db.execute('SELECT classification FROM attempts ORDER BY number')]
                unique = db.execute('SELECT count(*) FROM observations').fetchone()[0]
            result = dict(status='PASS' if classifications == ['new','duplicate'] and unique == 1 else 'FAIL',
                          classifications=classifications,unique=unique,first_exit=first.returncode)
            (run/'summary.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result))
            assert result['status']=='PASS'
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
