import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('spikes/SP-03/tests').resolve()))
from test_alignment import obs, T, timedelta
rows=[obs(20),obs(25,seq=2,quality='unknown',value={'wet':None})]
unknown={'state':'unknown','age_sec':None,'coverage_ratio':0.0}
case=dict(config=dict(width=30,lateness=2,ttl=10,flow_threshold=0.1),window_ends=[(T+timedelta(seconds=30)).isoformat()], observations=rows, expected_summaries=[dict(flow=unknown,water=dict(state='unknown',age_sec=None,coverage_ratio=5/30),presence=unknown)])
Path('spikes/SP-03/data/r02_case.json').write_text(json.dumps(case,indent=2),encoding='utf-8')
