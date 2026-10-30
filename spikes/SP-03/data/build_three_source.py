"""Synthetic fixture builder using standard library only; expected values are hand-authored."""
import json
from pathlib import Path
from datetime import datetime,timedelta,timezone
BASE=Path(__file__).resolve().parent
T=datetime(2026,10,29,tzinfo=timezone.utc)
rows=[]
for t in range(0,31,5):
    for sensor in ('flow','water','presence'):
        value=({'pulse_count':5,'interval_ms':5000,'estimated_lpm':6.0,'calibration_id':'synthetic-only'} if sensor=='flow' else {'wet':t>=30} if sensor=='water' else {'present':None if t==25 else True,'moving':None if t==25 else False,'still':None if t==25 else True})
        rows.append(dict(schema_version='1.1',observation_id=f'{sensor}-{t}',device_id='demo',sensor_type=sensor,boot_id='boot-a',seq=t//5,uptime_ms=t*1000,event_time=(T+timedelta(seconds=t)).isoformat(),received_at=(T+timedelta(seconds=t+(1 if sensor=='water' else 0))).isoformat(),time_basis='DEVICE_SYNCED',value=value,quality='unknown' if sensor=='presence' and t==25 else 'valid',source='simulation'))
case=dict(metadata=dict(synthetic=True,prototype_only=True),config=dict(width=30,lateness=2,ttl=10),window_ends=[(T+timedelta(seconds=t)).isoformat() for t in (30,35)],observations=rows,expected_summaries=[dict(flow=dict(state='active',age_sec=0.0,coverage_ratio=1.0),water=dict(state='wet',age_sec=0.0,coverage_ratio=1.0),presence=dict(state='present',age_sec=0.0,coverage_ratio=25/30)),dict(flow=dict(state='unknown',age_sec=None,coverage_ratio=25/30),water=dict(state='wet',age_sec=5.0,coverage_ratio=1.0),presence=dict(state='present',age_sec=5.0,coverage_ratio=25/30))])
(BASE/'r06_three_source.json').write_text(json.dumps(case,indent=2),encoding='utf-8')
