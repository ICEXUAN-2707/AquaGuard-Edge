"""R02 basic flow features; no persistence or complete FeatureWindow output."""
from datetime import timedelta
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from edge.contracts.models import AlignedWindow, validate_raw_observation


def calculate(window, rows, *, threshold=0.1):
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError('invalid threshold')
    w=AlignedWindow.model_validate(window)
    observations=[validate_raw_observation(r) for r in rows]
    indexed={}
    for r in observations:
        if r.observation_id in indexed:
            raise ValueError('duplicate observation identity')
        indexed[r.observation_id]=r
    if any(ref not in indexed for ref in w.source_observation_ids):
        raise ValueError('missing observation reference')
    selected=[indexed[ref] for ref in w.source_observation_ids]
    if any(r.device_id!=w.device_id for r in selected):
        raise ValueError('device mismatch')
    sources={r.source for r in selected}
    origin='mixed' if len(sources)>1 else next(iter(sources)) if sources else 'unknown'
    if origin!=w.origin:
        raise ValueError('origin mismatch')
    spans=[]
    for r in selected:
        if r.sensor_type!='flow' or r.quality!='valid':
            continue
        if not math.isfinite(r.value.estimated_lpm):
            raise ValueError('non-finite flow value')
        t=r.event_time or r.received_at
        if t>r.received_at or r.received_at>w.published_at or t>w.window_end:
            raise ValueError('referenced flow outside time policy')
        a=max(w.window_start,t-timedelta(milliseconds=r.value.interval_ms))
        b=min(w.window_end,t)
        if a<b:
            spans.append((a,b,r.value.estimated_lpm))
    spans.sort()
    if any(spans[i][0]<spans[i-1][1] for i in range(1,len(spans))):
        raise ValueError('overlapping flow intervals require explicit resolution')
    durations=[(b-a).total_seconds() for a,b,q in spans]
    valid=math.fsum(durations)
    width=(w.window_end-w.window_start).total_seconds()
    return dict(flow_mean_lpm=math.fsum(d*q for d,(_,_,q) in zip(durations,spans))/valid if valid else None,
                flow_max_lpm=max((q for a,b,q in spans),default=None),
                flow_active_ratio=math.fsum(d for d,(_,_,q) in zip(durations,spans) if q>threshold)/valid if valid else None,
                flow_coverage_ratio=valid/width,valid_flow_sec=valid,
                window_id=w.window_id,origin=origin,feature_version='m4-r02-v1')

