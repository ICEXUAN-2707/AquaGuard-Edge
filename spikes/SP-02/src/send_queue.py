"""Prototype publisher journal; broker ACK is transport evidence only."""
import argparse
import json
import sqlite3
import threading
from pathlib import Path

import paho.mqtt.client as mqtt


class SendQueue:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, payload TEXT NOT NULL, confirmed INTEGER NOT NULL DEFAULT 0)')
        self.db.commit()

    def enqueue(self, row):
        payload = json.dumps(row, sort_keys=True, separators=(',', ':'))
        with self.db:
            old = self.db.execute('SELECT payload FROM pending WHERE id=?', (row['observation_id'],)).fetchone()
            if old and old[0] != payload:
                raise ValueError('queued identity content conflict')
            self.db.execute('INSERT OR IGNORE INTO pending(id,payload) VALUES (?,?)', (row['observation_id'], payload))

    def flush(self, send):
        for identifier, payload in self.db.execute('SELECT id,payload FROM pending WHERE confirmed=0 ORDER BY rowid').fetchall():
            send(payload)  # Exceptions leave this measurement pending for retry.
            with self.db:
                self.db.execute('UPDATE pending SET confirmed=1 WHERE id=?', (identifier,))

    def pending(self):
        return self.db.execute('SELECT count(*) FROM pending WHERE confirmed=0').fetchone()[0]

    def close(self):
        self.db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['enqueue','flush','status'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--port', type=int, default=1883)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    queue = SendQueue(args.directory/'send-queue.sqlite')
    try:
        if args.mode == 'enqueue':
            for line in (args.directory/'manifest.jsonl').read_text(encoding='utf-8').splitlines():
                queue.enqueue(json.loads(line))
        elif args.mode == 'flush':
            ready = threading.Event()
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='sp02-durable-publisher')
            def connected(c, userdata, flags, reason, properties):
                if not reason.is_failure:
                    ready.set()
            client.on_connect = connected
            client.connect('127.0.0.1',args.port,30)
            client.loop_start()
            try:
                if not ready.wait(10):
                    raise TimeoutError('connection timeout')
                def send(payload):
                    info = client.publish('prototype/aquaguard/prototype01/observation',payload,qos=1)
                    info.wait_for_publish(timeout=10)
                    if not info.is_published():
                        raise TimeoutError('transport acknowledgement timeout')
                queue.flush(send)
            finally:
                client.disconnect()
                client.loop_stop()
        print(json.dumps(dict(pending=queue.pending())))
    finally:
        queue.close()


if __name__ == '__main__':
    main()
