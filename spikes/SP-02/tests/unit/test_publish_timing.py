import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

SOURCE=Path(__file__).resolve().parents[2]/'src'
sys.path.insert(0,str(SOURCE))
spec=importlib.util.spec_from_file_location('timed_mqtt_cli',SOURCE/'cli.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@pytest.mark.parametrize('mode',['success','failed_puback','stop'])
def test_publish_timing_and_owned_stop_file_without_network(tmp_path,monkeypatch,mode):
    rows=[dict(observation_id='id-1'),dict(observation_id='id-2')]
    (tmp_path/'manifest.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    stop=tmp_path/'stop.request';published=[];closed=[]
    class Client:
        def reconnect_delay_set(self,**kwargs):pass
        def connect(self,*args):pass
        def loop_start(self):self.on_connect(self,None,None,SimpleNamespace(is_failure=False),None)
        def publish(self,topic,line,**kwargs):
            published.append(line)
            if mode=='stop':stop.touch()
            return SimpleNamespace(wait_for_publish=lambda **kwargs:None,is_published=lambda:mode!='failed_puback')
        def disconnect(self):closed.append('disconnect')
        def loop_stop(self):closed.append('loop_stop')
    monkeypatch.setattr(module.mqtt,'Client',lambda *args,**kwargs:Client())
    monkeypatch.setattr(sys,'argv',['cli','publish','--directory',str(tmp_path),'--timing-evidence','--stop-file',str(stop)])
    if mode=='failed_puback':
        with pytest.raises(TimeoutError):module.main()
    else:module.main()
    timings=[json.loads(line) for line in (tmp_path/'publisher-timings.jsonl').read_text().splitlines()]
    assert len(timings)==(2 if mode=='success' else 1)
    assert timings[0]['scope']=='publish_attempt'
    assert timings[0]['puback_returned']==(mode!='failed_puback')
    assert closed==['disconnect','loop_stop']
