import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('spikes/SP-03/tests').resolve()))
sys.path.insert(0,str(Path('spikes/SP-03/src').resolve()))
from test_alignment import obs,T,timedelta
from stream import Stream
out={}
s=Stream('demo',T+timedelta(seconds=30),capacity=1)
s.push(obs(1))
try:s.push(obs(100,seq=2));out['capacity_before_expiry']='accepted'
except Exception as e:out['capacity_before_expiry']=str(e)
s=Stream('demo',T+timedelta(seconds=30))
s.push(obs(25))
s.push(obs(100,26,boot='b'))
out['future_new_boot_water_state']=s.advance(T+timedelta(seconds=32))[0]['windows'][0]['sensor_summary']['water']['state']
out['future_new_boot_retired']=sorted(s.retired)
s=Stream('demo',T+timedelta(seconds=30))
s.push(obs(25))
s.advance(T+timedelta(seconds=32))
packets=s.push(obs(30,32,seq=2))
out['same_deadline_arrival_after_timer_audit']=packets[-1]['audit'][0]['code']
print(json.dumps(out,indent=2))

