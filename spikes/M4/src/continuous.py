"""R04 historical replay oracle for continuous features, not a persistent engine."""
from datetime import timedelta
import math
from edge.contracts.models import validate_raw_observation


def continuous_features(rows,end,*,ttl=10,lateness=2,threshold=0.1,ttl_by_source=None):
    if not all(math.isfinite(v) for v in (ttl,lateness,threshold)) or ttl<=0 or lateness<0 or threshold<0 or end.tzinfo is None:
        raise ValueError('invalid temporal configuration')
    ttls={s:ttl for s in ("flow","water","presence")}
    if ttl_by_source is not None:
        if set(ttl_by_source)!=set(ttls) or any(not math.isfinite(v) or v<=0 for v in ttl_by_source.values()):
            raise ValueError('invalid source TTL')
        ttls.update(ttl_by_source)
    observations=[validate_raw_observation(r) for r in rows]
    if len({r.device_id for r in observations})>1:
        raise ValueError('one device required')
    observations=[r for r in observations if r.received_at<=end+timedelta(seconds=lateness) and (r.event_time or r.received_at)<=end]
    if len({r.boot_id for r in observations})>1:
        raise ValueError('cross-boot history unsupported')
    if len({r.observation_id for r in observations})!=len(observations):
        raise ValueError('duplicate history identity')
    spans={}; terminals={}
    for sensor in ('flow','water','presence'):
        source=sorted([r for r in observations if r.sensor_type==sensor],key=lambda r:(r.event_time or r.received_at,r.seq,r.observation_id))
        pieces=[];terminal=None
        for i,r in enumerate(source):
            t=r.event_time or r.received_at
            if t>r.received_at:
                raise ValueError('future event')
            valid=r.quality=='valid'
            if sensor=='flow':
                if not math.isfinite(r.value.estimated_lpm):
                    raise ValueError('non-finite flow')
                a,b=t-timedelta(milliseconds=r.value.interval_ms),t
                value=r.value.estimated_lpm>threshold if valid else None
            else:
                a=t
                b=min(t+timedelta(seconds=ttls[sensor]),(source[i+1].event_time or source[i+1].received_at) if i+1<len(source) else end,end)
                value=(r.value.wet if sensor=='water' else r.value.present) if valid else None
            if sensor=='flow':
                terminal=value if t==end else None
            else:
                terminal=value if end<t+timedelta(seconds=ttls[sensor]) else None
            if a<b:
                if pieces and a<pieces[-1][1]:
                    raise ValueError('overlapping history')
                pieces.append((a,b,value))
        spans[sensor]=pieces;terminals[sensor]=terminal
    def streak(pieces,terminal,target):
        if terminal is None:return None
        if terminal!=target:return 0.0
        cursor=end
        for a,b,v in reversed(pieces):
            if b!=cursor or v!=target:break
            cursor=a
        return (end-cursor).total_seconds()
    # Intersection of active flow and absent presence, without extrapolating gaps.
    intersection=[]
    for a,b,f in spans['flow']:
        if f is not True:continue
        for c,d,p in spans['presence']:
            left,right=max(a,c),min(b,d)
            if p is False and left<right:intersection.append((left,right,True))
    intersection.sort()
    pair=None if terminals['flow'] is None or terminals['presence'] is None else terminals['flow'] and not terminals['presence']
    return dict(flow_streak_sec=streak(spans['flow'],terminals['flow'],True),
                water_contact_sec=streak(spans['water'],terminals['water'],True),
                absence_after_flow_sec=streak(intersection,pair,True))
