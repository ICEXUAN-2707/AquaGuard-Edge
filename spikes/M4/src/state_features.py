"""R03 experimental window-local state features. No continuous checkpoints."""
from datetime import timedelta
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'SP-03/src'))
from alignment import align
from basic_flow import calculate
from transitions import count_transitions
from edge.contracts.models import AlignedWindow,validate_raw_observation


def state_features(window, rows, *, alignment_config):
    w=AlignedWindow.model_validate(window)
    probe=align([], [w.window_end], **alignment_config)
    expected=probe['windows'][0]
    if expected['alignment_config_version']!=w.alignment_config_version:
        raise ValueError('alignment configuration version mismatch')
    if (w.window_end-w.window_start).total_seconds()!=probe['config']['width']:
        raise ValueError('window width mismatch')
    flow=calculate(window,rows,threshold=probe['config']['flow_threshold'])
    selected={r['observation_id']:validate_raw_observation(r) for r in rows}
    refs=[selected[key] for key in w.source_observation_ids]
    if len({r.boot_id for r in refs})>1:
        raise ValueError('cross-boot feature policy not yet supported')
    flow_segments=[]
    for r in refs:
        if r.sensor_type=="flow" and r.quality=="valid":
            t=r.event_time or r.received_at
            a=max(w.window_start,t-timedelta(milliseconds=r.value.interval_ms))
            if a<t:
                flow_segments.append((a,t,r.value.estimated_lpm>probe["config"]["flow_threshold"]))
    output={"flow_change_count":count_transitions(flow_segments)}
    coverage={'flow':flow['flow_coverage_ratio']}
    for sensor in ('water','presence'):
        ordered=sorted([r for r in refs if r.sensor_type==sensor],key=lambda r: (r.event_time or r.received_at,r.seq,r.observation_id))
        segments=[]
        end_value=None
        for i,r in enumerate(ordered):
            t=r.event_time or r.received_at
            if t>r.received_at or t>w.window_end or r.received_at>w.published_at:
                raise ValueError('referenced state outside time policy')
            next_t=(ordered[i+1].event_time or ordered[i+1].received_at) if i+1<len(ordered) else w.window_end
            expiry=t+timedelta(seconds=probe['config']['ttl_by_source'][sensor])
            value=r.value.wet if sensor=='water' else r.value.present
            a,b=max(t,w.window_start),min(next_t,expiry,w.window_end)
            if r.quality=='valid' and value is not None and a<b:
                segments.append((a,b,value))
            end_value=value if r.quality=='valid' and w.window_end<expiry else None
        duration=sum((b-a).total_seconds() for a,b,v in segments)
        coverage[sensor]=duration/(w.window_end-w.window_start).total_seconds()
        endpoint=None
        if len(ordered)>=2:
            current,previous=ordered[-1],ordered[-2]
            t=current.event_time or current.received_at
            previous_t=previous.event_time or previous.received_at
            value=current.value.wet if sensor=='water' else current.value.present
            if t==w.window_end and current.quality=='valid' and value is not None and previous.quality=='valid' and previous_t<t and t<previous_t+timedelta(seconds=probe['config']['ttl_by_source'][sensor]):
                endpoint=(t,value)
        count=count_transitions(segments,endpoint=endpoint)
        if sensor=='water':
            output['water_contact']=end_value
        else:
            output.update(presence_state='unknown' if end_value is None else 'present' if end_value else 'absent',
                          presence_occupied_ratio=sum((b-a).total_seconds() for a,b,v in segments if v)/duration if duration else None,
                          presence_transition_count=count)
        if abs(coverage[sensor]-getattr(w.sensor_summary,sensor).coverage_ratio)>1e-9:
            raise ValueError('state coverage differs from M3')
    output['data_coverage_ratio']=sum(coverage.values())/3
    output['coverage_by_source']=coverage
    output['alignment_config_version']=w.alignment_config_version
    output['feature_version']='m4-r05-v1'
    return output
