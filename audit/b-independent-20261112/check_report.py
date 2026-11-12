import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent
a = json.loads((out/'r07/report.json').read_text(encoding='utf-8'))
b = json.loads((root/'spikes/SP-04/evidence/r07/report.json').read_text(encoding='utf-8'))
result = {'different_top_keys': [k for k in a if a[k] != b.get(k)], 'equal_sections': {k: a[k] == b[k] for k in ('metrics', 'trials', 'online_offline', 'fallback_check')}, 'trial_keys': list(a['trials'][0])}
(out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
