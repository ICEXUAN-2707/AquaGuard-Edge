import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('sp02queue', Path(__file__).parents[2]/'src/send_queue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_failed_send_survives_restart(tmp_path):
    path = tmp_path/'queue.sqlite'
    queue = module.SendQueue(path)
    row = {'observation_id':'stable','value':1}
    queue.enqueue(row)
    queue.enqueue(row)
    def unavailable(payload):
        raise ConnectionError('offline')
    with pytest.raises(ConnectionError):
        queue.flush(unavailable)
    queue.close()
    queue = module.SendQueue(path)
    assert queue.pending() == 1
    sent = []
    queue.flush(sent.append)
    assert len(sent) == 1 and queue.pending() == 0
    queue.close()


def test_content_conflict(tmp_path):
    queue = module.SendQueue(tmp_path/'queue.sqlite')
    queue.enqueue({'observation_id':'a','value':1})
    with pytest.raises(ValueError):
        queue.enqueue({'observation_id':'a','value':2})
    queue.close()
