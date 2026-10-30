"""R02 trusted local checkpoint gate. Does not classify READY cases."""
import json,math,sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'M4/src'))
from checkpoint import restore,FEATURE_VERSION
from alignment import align
from edge.contracts.models import FeatureWindow,AlignedWindow

DEFAULT=json.loads((Path(__file__).resolve().parents[1]/'data/rules_config.json').read_text(encoding='utf-8-sig'))

def gate(payload,now,*,checkpoint_root,config=None):
    config=dict(DEFAULT if config is None else config)
    if set(config)!=set(DEFAULT):raise ValueError("rule configuration keys mismatch")
    if not isinstance(config["rule_version"],str) or not config["rule_version"].strip():raise ValueError("invalid rule version")
    if config["evaluation_policy"]!="fixed_publication_time" or config["flow_threshold_policy"]!="inherit_alignment_config":raise ValueError("unsupported rule policy")
    for key in ('unattended_sec','min_flow_coverage','min_presence_coverage','idle_confirm_sec','max_window_age_sec'):
        value=config[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError('invalid rule configuration')
    if any(config[k]>1 for k in ('min_flow_coverage','min_presence_coverage')):raise ValueError('invalid coverage threshold')
    fw=FeatureWindow.model_validate(payload)
    if fw.feature_version!=FEATURE_VERSION:raise ValueError('unsupported feature version')
    root=Path(checkpoint_root).resolve(strict=True)
    path=Path(fw.state_checkpoint_ref).resolve(strict=True)
    if not path.is_relative_to(root):raise ValueError('checkpoint outside trusted root')
    restored=restore(path)
    if restored['feature_window']!=fw.model_dump(mode='json'):raise ValueError('feature/checkpoint mismatch')
    window=AlignedWindow.model_validate(restored['last_window'])
    if now.tzinfo is None or now<window.published_at:raise ValueError('invalid evaluation time')
    flow=window.sensor_summary.flow;presence=window.sensor_summary.presence
    reason=None
    if (now-window.window_end).total_seconds()>config['max_window_age_sec']:reason='WINDOW_STALE'
    elif fw.missing_mask.flow:reason='FLOW_MISSING'
    elif flow.state=='unknown':reason='FLOW_UNKNOWN'
    elif flow.coverage_ratio<config['min_flow_coverage']:reason='FLOW_COVERAGE_LOW'
    elif flow.state=='active' and (fw.missing_mask.presence or presence.state=='unknown'):reason='PRESENCE_UNKNOWN'
    elif flow.state=='active' and presence.coverage_ratio<config['min_presence_coverage']:reason='PRESENCE_COVERAGE_LOW'
    # Quality and classification are separate: a ready IDLE path can still lack presence/water.
    degraded=any(getattr(window.sensor_summary,s).state=='unknown' or getattr(window.sensor_summary,s).coverage_ratio<1 for s in ('flow','water','presence')) or bool(window.quality_flags)
    quality='UNAVAILABLE' if fw.missing_mask.flow else 'DEGRADED' if reason or degraded else 'VALID'
    idle=None
    if reason is None and flow.state=='inactive':
        threshold=align([],[],**restored['alignment_config'])['config']['flow_threshold']
        refs=set(window.source_observation_ids)
        spans=[]
        from edge.contracts.models import validate_raw_observation
        for row in restored['history']:
            r=validate_raw_observation(row)
            if r.observation_id in refs and r.sensor_type=='flow' and r.quality=='valid':
                t=r.event_time or r.received_at
                spans.append((t-timedelta(milliseconds=r.value.interval_ms),t,r.value.estimated_lpm<=threshold))
        cursor=window.window_end
        for a,b,inactive in reversed(sorted(spans)):
            if b!=cursor or not inactive:break
            cursor=a
        idle=(window.window_end-cursor).total_seconds()
    return dict(status='UNKNOWN' if reason else 'READY',reason=reason,data_quality=quality,
                idle_sec=idle,window=window.model_dump(mode='json'),feature_window=fw.model_dump(mode='json'),config=config,
                evaluated_at=now.isoformat())
