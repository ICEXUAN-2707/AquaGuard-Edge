import json
from pathlib import Path
from datetime import datetime,timedelta
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stream import Stream
from alignment import align
BASE=Path(__file__).resolve().parents[1]
def test_three_source_golden_and_stream_equivalence():
    case=json.loads((BASE/'data/r06_three_source.json').read_text(encoding='utf-8'))
    ends=[datetime.fromisoformat(t) for t in case['window_ends']]
    batch=align(case['observations'],ends,**case['config'])
    assert [w['sensor_summary'] for w in batch['windows']]==case['expected_summaries']
    assert all(w['origin']=='simulation' for w in batch['windows'])
    assert 'presence-25' in batch['windows'][0]['source_observation_ids']
    stream=Stream('demo',ends[0],**case['config'])
    packets=[]
    for row in sorted(case['observations'],key=lambda r:(r['received_at'],r['observation_id'])):
        packets.extend(stream.push(row))
    packets.extend(stream.advance(ends[-1]+timedelta(seconds=2)))
    assert [w for p in packets for w in p['windows']]==batch['windows']
