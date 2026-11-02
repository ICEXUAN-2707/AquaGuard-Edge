"""Synthetic scenario factory with independent operation annotations."""
from datetime import datetime,timedelta,timezone
T=datetime(2026,10,29,tzinfo=timezone.utc)

def observations(*,leave=20,attended=False,idle=False,missing_presence=False):
    rows=[]
    for sensor in ('flow','water','presence'):
        if sensor=='presence' and missing_presence:continue
        times=list(range(0,31,5))
        if sensor=='presence' and leave not in times:times.append(leave)
        for seq,t in enumerate(sorted(times)):
            if sensor=='flow' and t==0:continue
            present=attended or t<leave
            value=dict(pulse_count=1,interval_ms=5000,estimated_lpm=0.0 if idle else 6.0,calibration_id='synthetic') if sensor=='flow' else dict(wet=False) if sensor=='water' else dict(present=present,moving=False,still=present)
            rows.append(dict(schema_version='1.1',observation_id=f'{sensor}-{seq}',device_id='demo',sensor_type=sensor,boot_id='a',seq=seq,uptime_ms=int(t*1000),event_time=(T+timedelta(seconds=t)).isoformat(),received_at=(T+timedelta(seconds=t)).isoformat(),time_basis='DEVICE_SYNCED',value=value,quality='valid',source='simulation'))
    return rows
