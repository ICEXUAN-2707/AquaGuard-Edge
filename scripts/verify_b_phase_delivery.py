"""Final read-only evidence verification and captured targeted regression."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from build_b_sim_dataset import verify
ROOT=Path(__file__).resolve().parents[1]

def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((ROOT/'B_DELIVERY_MANIFEST.json').read_text())
    for entry in manifest['files']:
        p=ROOT/entry['path']
        if p.stat().st_size!=entry['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('delivery digest mismatch: '+str(p))
    dataset=verify(ROOT/'deliverables/B-SIM-001')
    model_dir=ROOT/'deliverables/B-PROXY-MODEL-001'
    lock=json.loads((model_dir/'model.lock.json').read_text())
    model_hash=hashlib.sha256((model_dir/'model.json').read_bytes()).hexdigest()
    if model_hash!=lock['model_sha256']:raise ValueError('model lock mismatch')
    report=json.loads((ROOT/'deliverables/B-PROXY-EVAL-001/report.json').read_text())
    pair=json.loads((ROOT/'deliverables/B-PROXY-EVAL-001/paired_analysis.json').read_text())
    predictions=(ROOT/'deliverables/B-PROXY-EVAL-001/predictions.jsonl').read_bytes()
    if model_hash!=report['model_sha256'] or hashlib.sha256(predictions).hexdigest()!=pair['predictions_sha256']:raise ValueError('report linkage mismatch')
    fallback=json.loads((ROOT/'deliverables/B-PROXY-FALLBACK-001/fallback_report.json').read_text())
    if len(fallback['records'])!=162 or not all(r['passed'] and r['c2_value'] is r['fallback_value'] for r in fallback['records']):raise ValueError('fallback evidence mismatch')
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','scripts','-p','test_b*.py','-v'],cwd=ROOT,capture_output=True,text=True)
    (output/'unittest.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    summary=dict(scope='offline synthetic proxy engineering phase only',delivery_files_verified=len(manifest['files']),dataset=dataset,
                 model_sha256=model_hash,report_links='PASS',fallback_checks=162,regression_exit_code=result.returncode,
                 regression_log_sha256=hashlib.sha256((output/'unittest.log').read_bytes()).hexdigest(),
                 tests_expected=17,test_run_passed=result.returncode==0)
    (output/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    if result.returncode:raise RuntimeError('targeted regression failed')
    return summary

if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
