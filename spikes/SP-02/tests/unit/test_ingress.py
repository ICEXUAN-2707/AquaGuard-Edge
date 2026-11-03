import sys
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]/'src'))
from core import Journal, sample
from ingress import process_message


def message(payload):
    return SimpleNamespace(topic='prototype/aquaguard/prototype01/observation', qos=1, retain=False, mid=12, payload=payload)


@pytest.mark.parametrize('payload', [json.dumps(sample()).encode(), b'not-json'])
def test_ack_after_durable_record(tmp_path, payload):
    journal = Journal(tmp_path/'test.sqlite')
    def ack(mid, qos):
        count = journal.db.execute('SELECT count(*) FROM attempts').fetchone()[0]
        count += journal.db.execute('SELECT count(*) FROM rejected').fetchone()[0]
        assert count == 1
    process_message(message(payload), journal, ack)
    journal.close()


@pytest.mark.parametrize('payload', [json.dumps(sample()).encode(), b'not-json'])
def test_storage_failure_never_acknowledged(payload):
    class Broken:
        def accept(self, row):
            raise OSError('disk unavailable')
        reject = accept
    acknowledgements = []
    with pytest.raises(OSError):
        process_message(message(payload), Broken(), lambda *args: acknowledgements.append(args))
    assert not acknowledgements


def test_actual_sqlite_readonly_failure_does_not_ack(tmp_path):
    journal = Journal(tmp_path/'readonly.sqlite')
    journal.db.execute('PRAGMA query_only=ON')
    acknowledgements = []
    with pytest.raises(sqlite3.OperationalError):
        process_message(message(json.dumps(sample()).encode()), journal, lambda *args: acknowledgements.append(args))
    assert not acknowledgements
    journal.close()


@pytest.mark.parametrize('payload,retained', [(b'\xff',False), (b'{',False), (json.dumps(sample()).encode(),True)])
def test_rejects_are_durable_and_acknowledged(tmp_path,payload,retained):
    journal = Journal(tmp_path/'reject.sqlite')
    msg = message(payload)
    msg.retain = retained
    acknowledgements = []
    result = process_message(msg,journal,lambda *args: acknowledgements.append(args))
    assert result['classification'] == 'invalid'
    assert len(acknowledgements) == 1
    assert journal.db.execute('SELECT count(*) FROM rejected').fetchone()[0] == 1
    assert not journal.export()
    journal.close()
