"""Reproducible M4 demo, no pytest dependency."""
import json,sys
from datetime import datetime
from pathlib import Path
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from checkpoint import save,restore
from alignment import align
case=json.loads((BASE.parent/'SP-03/data/r06_three_source.json').read_text(encoding='utf-8'))
windows=align(case['observations'],[datetime.fromisoformat(t) for t in case['window_ends']],**case['config'])['windows']
results=[]
for window in windows:
    result=save(BASE/'evidence/checkpoints',window,case['observations'],alignment_config=case['config'])
    assert restore(result['state_checkpoint_ref'])['feature_window']==result
    results.append(result)
(BASE/'evidence/r07_feature_windows.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(results)} candidate FeatureWindows saved and restored consistently')
