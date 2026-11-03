"""Classify actual M4 demo artifacts under a controlled checkpoint root."""
import json,sys
from pathlib import Path
from datetime import datetime
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from rules import classify
from checkpoint import restore
root=BASE.parent/'SP-03-features/evidence/checkpoints'
inputs=json.loads((BASE.parent/'SP-03-features/evidence/r07_feature_windows.json').read_text(encoding='utf-8'))
results=[]
for payload in inputs:
    restored=restore(payload['state_checkpoint_ref'])
    now=datetime.fromisoformat(restored['last_window']['published_at'].replace('Z','+00:00'))
    results.append(classify(payload,now,checkpoint_root=root))
(BASE/'evidence/r03_assessments.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print([r['situation'] for r in results])
