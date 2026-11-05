"""prototype_only: consume B checkpoint-backed simulation output, no safety writes."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/SP-03/src"))
sys.path.insert(0,str(ROOT/"spikes/SP-03-features/src"))
sys.path.insert(0,str(ROOT/"spikes/SP-04/src"))
from gates import gate
from rules import classify
from edge.contracts.models import _aware


def publish_window(queries,feature_window,*,now,checkpoint_root,config=None,safety_signals=None):
    """Trusted local call per new feature window; caller owns input scheduling.

    Recompute from content-addressed B checkpoint under an approved directory.
    Source authorization and actual hardware clock evidence remain out of scope.
    """
    clock=_aware(now)
    context=gate(feature_window,clock,checkpoint_root=checkpoint_root,config=config)
    if context["reason"]=="WINDOW_STALE":
        raise ValueError("stale B window cannot refresh projections")
    window=context["window"]
    if window["origin"]!="simulation":
        raise ValueError("bridge currently permits simulation only")
    assessment=classify(feature_window,clock,checkpoint_root=checkpoint_root,config=config)
    ttl=context["config"]["max_window_age_sec"]
    if ttl<=0:
        raise ValueError("positive projection validity interval required")
    # Preserve the evidence boundary: repeated evaluation must not extend expiry.
    captured=window["window_end"]
    with queries.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        queries.publish("live",dict(schema_version="1.1",device_id=window["device_id"],captured_at=captured,
            sensor_summary=window["sensor_summary"],data_quality=context["data_quality"],cloud_status="UNKNOWN",origin=window["origin"]),
            captured_at=captured,ttl_seconds=ttl,_connection=db)
        queries.publish("assessment",dict(schema_version="1.1",assessment=assessment,safety_signals=safety_signals or []),
            captured_at=captured,ttl_seconds=ttl,_connection=db)
    return assessment
