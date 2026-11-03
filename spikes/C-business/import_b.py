"""Import B historical simulation artifacts into a NEW offline demo database."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from edge.contracts.models import AlignedWindow, FeatureWindow, SituationAssessment
from policy import Policy
from projections import Projections


def prepare(windows,features,assessments):
    def indexed(rows,model):
        values=[model.model_validate(row) for row in rows]
        result={v.window_id:v for v in values}
        if len(result)!=len(values):
            raise ValueError("duplicate window identity")
        return result
    windows=indexed(windows,AlignedWindow)
    features=indexed(features,FeatureWindow)
    assessments=indexed(assessments,SituationAssessment)
    if not assessments or windows.keys()!=features.keys() or windows.keys()!=assessments.keys():
        raise ValueError("window/feature/assessment sets must match and be nonempty")
    result=[]
    for key,assessment in assessments.items():
        window,feature=windows[key],features[key]
        if len({window.device_id,feature.device_id,assessment.device_id})!=1 or {window.origin,feature.origin,assessment.origin}!={"simulation"}:
            raise ValueError("device mismatch or non-simulation artifact")
        result.append((window,assessment))
    return sorted(result,key=lambda pair:pair[0].window_end)


def import_artifacts(path,windows,features,assessments,*,ttl_seconds):
    Policy(ttl_seconds,1)  # Reuse finite positive duration validation, no business default.
    prepared=prepare(windows,features,assessments)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb"):
        pass
    queries=Projections(path)
    for window,assessment in prepared:
        captured=window.window_end.isoformat()
        queries.publish("live",dict(schema_version="1.1",device_id=window.device_id,captured_at=captured,
            sensor_summary=window.sensor_summary.model_dump(mode="json"),data_quality=assessment.data_quality,
            cloud_status="UNKNOWN",origin="simulation"),captured_at=captured,ttl_seconds=ttl_seconds)
        queries.publish("assessment",dict(schema_version="1.1",assessment=assessment.model_dump(mode="json"),safety_signals=[]),
                        captured_at=window.published_at.isoformat(),ttl_seconds=ttl_seconds)
    return len(prepared)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--windows",type=Path,required=True)
    parser.add_argument("--features",type=Path,required=True)
    parser.add_argument("--assessments",type=Path,required=True)
    parser.add_argument("--ttl",type=float,required=True)
    args=parser.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    count=import_artifacts(args.db,read(args.windows)["windows"],read(args.features),read(args.assessments),ttl_seconds=args.ttl)
    print(json.dumps(dict(prototype_only=True,imported_windows=count,historical=True)))
