"""prototype_only local MQTT runner. Run from repository root."""
import argparse
import json
import sys
import threading
import time
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core import Journal, normalize, sample
from ingress import process_message, observation_topic
import paho.mqtt.client as mqtt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['generate', 'publish', 'subscribe', 'export'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--device-id', default='prototype01', help='trusted simulation device identity')
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--interval', type=float, default=0, help='seconds between publications; flow feature experiments need compatible measured intervals')
    parser.add_argument('--persistent-session', action='store_true')
    parser.add_argument('--crash-after-commit', action='store_true', help='prototype fault injection: exit before MQTT ACK')
    parser.add_argument('--timing-evidence',action='store_true',help='record subscriber commit and ACK submission timings; not broker confirmation')
    args = parser.parse_args()
    try:
        topic = observation_topic(args.device_id)
    except ValueError as exc:
        parser.error(str(exc))
    if args.count < 1 or args.seconds <= 0 or args.interval < 0:
        parser.error('count and seconds must be positive')
    args.directory.mkdir(parents=True, exist_ok=True)
    data = args.directory / 'manifest.jsonl'
    if args.mode == 'generate':
        data.write_text(''.join(json.dumps(sample(i, ['flow','water','presence'][i % 3], device_id=args.device_id)) + '\n' for i in range(args.count)), encoding='utf-8')
        return
    if args.mode == 'export':
        journal = Journal(args.directory / 'journal.sqlite')
        rows = journal.export()
        (args.directory / 'accepted.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        journal.close()
        return
    ready = threading.Event()
    errors = []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='sp02-' + args.mode, protocol=mqtt.MQTTv311,
                         clean_session=not args.persistent_session, manual_ack=True)
    client.reconnect_delay_set(min_delay=1, max_delay=4)

    def event(kind, **details):
        with (args.directory / (args.mode + '-connections.jsonl')).open('a', encoding='utf-8') as log:
            log.write(json.dumps(dict(event=kind, utc=datetime.now(timezone.utc).isoformat(),
                                      monotonic=time.monotonic(), **details)) + '\n')

    def connected(c, userdata, flags, reason, properties):
        event('connected', reason=str(reason))
        if reason.is_failure:
            errors.append(str(reason))
            ready.set()
        elif args.mode == 'subscribe':
            c.subscribe(topic, qos=1)
        else:
            ready.set()

    def subscribed(c, userdata, mid, reasons, properties):
        event('subscribed', reasons=[str(r) for r in reasons])
        if any(r.is_failure for r in reasons):
            errors.append('subscription rejected')
        ready.set()

    def disconnected(c, userdata, flags, reason, properties):
        ready.clear()
        event('disconnected', reason=str(reason))

    def message(c, userdata, msg):
        timing={} if args.timing_evidence else None
        try:
            journal = Journal(args.directory / 'journal.sqlite')
            try:
                def after_commit():
                    if args.crash_after_commit:
                        os._exit(73)
                def acknowledge(mid, qos):
                    if c.ack(mid, qos) != mqtt.MQTT_ERR_SUCCESS:
                        raise RuntimeError('ack submission failed')
                record = process_message(msg, journal, acknowledge, after_commit, device_id=args.device_id,timing=timing)
            finally:
                journal.close()
            with (args.directory / 'received.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps(record) + '\n')
                log.flush()
            if record['classification'] == 'invalid':
                errors.append(record['error'])
        except Exception as exc:
            errors.append('processing/storage failure: ' + repr(exc))
            c.disconnect()  # Do not ACK on storage failure; persistent session can retry.
        finally:
            if timing is not None:
                timing['utc']=datetime.now(timezone.utc).isoformat()
                try:
                    with (args.directory/'subscriber-timings.jsonl').open('a',encoding='utf-8') as log:
                        log.write(json.dumps(timing)+'\n');log.flush();os.fsync(log.fileno())
                except OSError as exc:
                    errors.append('timing evidence failure: '+type(exc).__name__)
                    c.disconnect()

    client.on_connect, client.on_subscribe, client.on_message = connected, subscribed, message
    client.on_disconnect = disconnected
    client.connect('127.0.0.1', args.port, 30)
    client.loop_start()
    try:
        if not ready.wait(10) or errors:
            raise RuntimeError('connection/subscription failed: ' + repr(errors))
        print('READY', flush=True)
        if args.mode == 'publish':
            for line in data.read_text(encoding='utf-8').splitlines():
                info = client.publish(topic, line, qos=1, retain=False)
                info.wait_for_publish(timeout=10)
                if not info.is_published():
                    raise TimeoutError('publish confirmation timeout')
                if args.interval:
                    time.sleep(args.interval)
        else:
            threading.Event().wait(args.seconds)
        if errors:
            raise RuntimeError('ingress errors: ' + repr(errors))
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == '__main__':
    main()
