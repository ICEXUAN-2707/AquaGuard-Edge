"""Summarize diagnostic signals without assigning an unsupported root cause."""
import argparse
from collections import Counter
import json
from pathlib import Path


def analyze(samples):
    steady=[row for row in samples if row['elapsed_sec']>=45]
    timings=[row.get('runtime',{}).get('diagnostics',{}).get('timing') for row in samples]
    timings=[row for row in timings if row]
    bad=[]
    for row in steady:
        if row.get('live',{}).get('status')==200:continue
        diagnostic=row.get('runtime',{}).get('diagnostics',{})
        bad.append({'elapsed_sec':row['elapsed_sec'],'utc':row.get('utc'),
                    'status':row.get('live',{}).get('status'),
                    'estimated_suspend_seconds':row.get('estimated_suspend_seconds'),
                    'sample_gap_seconds':row.get('sample_gap_seconds'),
                    'projections':diagnostic.get('projections',[]),
                    'timing':diagnostic.get('timing')})
    return {'samples':len(samples),'steady_samples':len(steady),
            'steady_live_status_counts':dict(Counter(str(row.get('live',{}).get('status')) for row in steady)),
            'max_sample_gap_seconds':max((row.get('sample_gap_seconds') or 0 for row in samples),default=0),
            'max_estimated_suspend_seconds':max((row.get('estimated_suspend_seconds') or 0 for row in samples),default=0),
            'max_advance_seconds':max((row['max_advance_seconds'] for row in timings),default=None),
            'max_runtime_gap_seconds':max((row['max_gap_seconds'] for row in timings),default=None),
            'max_timer_failures':max((row['failures'] for row in timings),default=None),
            'unavailable_samples':bad,
            'note':'Diagnostics follow the live request and may reflect a later state. Missing suspend metrics are unknown, not proof of awake operation. Tiny clock differences are quantization noise; no automatic root-cause verdict.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples',type=Path)
    args=parser.parse_args()
    print(json.dumps(analyze([json.loads(line) for line in args.samples.read_text(encoding='utf-8').splitlines()]),indent=2))


if __name__=='__main__':main()
