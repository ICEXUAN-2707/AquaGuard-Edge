"""R06 unified experimental computation. Does not create checkpoint references."""
from state_features import state_features
from basic_flow import calculate
from continuous import continuous_features
from alignment import align
from edge.contracts.models import AlignedWindow,Features,validate_raw_observation


def compute(window,history,*,alignment_config):
    w=AlignedWindow.model_validate(window)
    parsed=[validate_raw_observation(r) for r in history]
    if any(r.device_id!=w.device_id for r in parsed):
        raise ValueError('history device mismatch')
    # Reconstruct the complete window, including lineage, to detect omitted or altered evidence.
    rebuilt=align(history,[w.window_end],**alignment_config)
    expected=rebuilt['windows'][0]
    if not parsed:
        expected['device_id']=w.device_id
        expected['window_id']=expected['window_id'].replace('demo:',w.device_id+':',1)
    if expected!=w.model_dump(mode='json'):
        raise ValueError('window/history/config mismatch')
    config=rebuilt['config']
    state=state_features(window,history,alignment_config=alignment_config)
    flow=calculate(window,history,threshold=config['flow_threshold'])
    temporal=continuous_features(history,w.window_end,ttl=config['ttl'],lateness=config['lateness'],threshold=config['flow_threshold'],ttl_by_source=config['ttl_by_source'])
    names=set(Features.model_fields)
    merged={k:v for result in (flow,state,temporal) for k,v in result.items() if k in names}
    features=Features.model_validate(merged).model_dump()
    refs=set(w.source_observation_ids)
    missing={s:not any(r.observation_id in refs and r.sensor_type==s and r.quality=='valid' for r in parsed) for s in ('flow','water','presence')}
    # No fabricated state_checkpoint_ref: this is deliberately not FeatureWindow yet.
    return dict(window_id=w.window_id,device_id=w.device_id,feature_version='m4-r06-v1',features=features,missing_mask=missing,origin=w.origin,prototype_only=True)
