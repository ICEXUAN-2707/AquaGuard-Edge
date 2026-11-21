import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from mqtt_awake_runner import system_required

@pytest.mark.parametrize('body_fails',[False,True])
def test_thread_power_state_restored_even_after_execution_error(body_fails):
    calls=[]
    def state(flags):calls.append(flags);return 0x80000002
    receipt=None
    try:
        with system_required(state) as receipt:
            assert calls==[0x80000001] and not receipt['restored']
            if body_fails:raise ValueError('execution failed')
    except ValueError:assert body_fails
    assert calls==[0x80000001,0x80000002] and receipt['restored']

def test_failed_request_never_enters_execution():
    with pytest.raises(OSError,match='request failed'):
        with system_required(lambda flags:0):pytest.fail('must not execute')

def test_failed_restore_is_not_reported_as_success():
    responses=iter([0x80000000,0])
    with pytest.raises(OSError,match='restore failed'):
        with system_required(lambda flags:next(responses)) as receipt:pass
    assert not receipt['restored']
