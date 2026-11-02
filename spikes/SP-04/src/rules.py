"""R03 deterministic rules; independent of water safety decisions."""
import hashlib
from gates import gate
from checkpoint import canonical
from edge.contracts.models import SituationAssessment

SEMANTIC_VERSION='m5-r03-v1'

def classify(payload,now,*,checkpoint_root,config=None):
    context=gate(payload,now,checkpoint_root=checkpoint_root,config=config)
    fw=context['feature_window'];window=context['window'];cfg=context['config']
    situation='UNKNOWN';reason=context['reason'];quality=context['data_quality']
    if context['status']=='READY':
        if window['sensor_summary']['flow']['state']=='inactive':
            if context['idle_sec'] is not None and context['idle_sec']>=cfg['idle_confirm_sec']:
                situation,reason='IDLE','IDLE_CONFIRMED'
            else:reason='IDLE_NOT_CONFIRMED'
        elif window['sensor_summary']['presence']['state']=='present':
            situation,reason='ATTENDED_FLOW','PRESENCE_DETECTED'
        else:
            duration=fw['features']['absence_after_flow_sec']
            if duration is not None and duration>=cfg['unattended_sec']:
                situation,reason='POSSIBLE_UNATTENDED_FLOW','UNATTENDED_DURATION_REACHED'
            else:reason='DURATION_NOT_REACHED'
    reasons=[reason]
    for sensor in ('water','presence'):
        summary=window['sensor_summary'][sensor]
        if summary['state']=='unknown' or summary['coverage_ratio']<1:
            reasons.append(sensor.upper()+'_EVIDENCE_DEGRADED')
    config_hash=hashlib.sha256(canonical(cfg)).hexdigest()[:16]
    version=SEMANTIC_VERSION+':'+config_hash
    # Stale requests get a distinct identity; fresh replay at another clock keeps the fixed-window identity.
    identity=dict(window_id=fw['window_id'],feature_version=fw['feature_version'],model_version=version,
                  evidence_digest=hashlib.sha256(canonical(dict(features=fw['features'],origin=fw['origin'],window=window))).hexdigest())
    if context['reason']=='WINDOW_STALE':identity['stale_evaluated_at']=context['evaluated_at']
    return SituationAssessment.model_validate(dict(schema_version='1.1',assessment_id=hashlib.sha256(canonical(identity)).hexdigest(),window_id=fw['window_id'],device_id=fw['device_id'],situation=situation,inference_mode='rules',model_version=version,model_score=None,data_quality=quality,reason_codes=sorted(set(reasons)),origin=fw['origin'])).model_dump(mode='json')
