"""Final read-only evidence verification and captured targeted regression."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from build_b_sim_dataset import verify
from b_training_inputs import verify_inputs
from b_bundle_checks import check_annotations
from b_evidence_checks import check_evidence
from train_b_proxy import checked
from experiment.ml import load_model
ROOT=Path(__file__).resolve().parents[1]

def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((ROOT/'B_DELIVERY_MANIFEST.json').read_text())
    for entry in manifest['files']:
        p=ROOT/entry['path']
        if p.stat().st_size!=entry['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('delivery digest mismatch: '+str(p))
    dataset=verify(ROOT/'deliverables/B-SIM-001')
    feature_dir=ROOT/'deliverables/B-PROXY-INPUTS-001'
    plan=json.loads((ROOT/'deliverables/B-CANDIDATE-PROXY-001/training_plan.lock.json').read_text())
    feature_manifest=json.loads((feature_dir/'manifest.json').read_text())
    if hashlib.sha256((feature_dir/'manifest.json').read_bytes()).hexdigest()!=plan['feature_manifest_sha256']:raise ValueError('feature manifest binding mismatch')
    rows=[json.loads(line) for line in checked(feature_dir/'features.jsonl',plan['parent_features_sha256']).splitlines()]
    label_dir=ROOT/'deliverables/B-CANDIDATE-PROXY-001'
    lm=json.loads(checked(label_dir/'manifest.json',plan['label_manifest_sha256']))
    checked(label_dir/'contract.json',lm['contract_sha256'])
    annotations=[json.loads(line) for line in checked(label_dir/'labels.jsonl',lm['label_sha256']).splitlines()]
    check_annotations(rows,annotations)
    verify_inputs(ROOT,feature_manifest,plan,rows)
    model_dir=ROOT/'deliverables/B-PROXY-MODEL-001'
    lock=json.loads((model_dir/'model.lock.json').read_text())
    model_hash=hashlib.sha256((model_dir/'model.json').read_bytes()).hexdigest()
    if model_hash!=lock['model_sha256']:raise ValueError('model lock mismatch')
    model=load_model(model_dir/'model.json')
    plan_hash=hashlib.sha256((label_dir/'training_plan.lock.json').read_bytes()).hexdigest()
    if lock['plan_sha256']!=plan_hash or model['training']['plan_sha256']!=plan_hash or model['training']['label_sha256']!=lm['label_sha256']:raise ValueError('model plan/label binding mismatch')
    checked(model_dir/'training_plan.lock.json',plan_hash)
    report=json.loads((ROOT/'deliverables/B-PROXY-EVAL-001/report.json').read_text())
    pair=json.loads((ROOT/'deliverables/B-PROXY-EVAL-001/paired_analysis.json').read_text())
    predictions=(ROOT/'deliverables/B-PROXY-EVAL-001/predictions.jsonl').read_bytes()
    if model_hash!=report['model_sha256'] or hashlib.sha256(predictions).hexdigest()!=pair['predictions_sha256']:raise ValueError('report linkage mismatch')
    fallback=json.loads((ROOT/'deliverables/B-PROXY-FALLBACK-001/fallback_report.json').read_text())
    protocol_path=model_dir/'P3_PROTOCOL.json'
    protocol_raw=checked(protocol_path,report['protocol_sha256'])
    if json.loads(protocol_raw.decode('utf-8-sig'))!=report['protocol'] or (ROOT/'deliverables/B-PROXY-EVAL-001/P3_PROTOCOL.json').read_bytes()!=protocol_raw:raise ValueError('protocol binding mismatch')
    if report['label_sha256']!=lm['label_sha256'] or report['predictions_sha256']!=hashlib.sha256(predictions).hexdigest():raise ValueError('prediction/label digest mismatch')
    record_rows=[json.loads(line) for line in predictions.splitlines()]
    check_evidence(record_rows,report,fallback,annotations,model_hash,plan['feature_manifest_sha256'])
    tests_discovered=unittest.defaultTestLoader.discover(str(ROOT/'scripts'),pattern='test_b*.py').countTestCases()
    if tests_discovered==0:raise ValueError('no regression tests discovered')
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','scripts','-p','test_b*.py','-v'],cwd=ROOT,capture_output=True,text=True)
    (output/'unittest.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    summary=dict(scope='offline synthetic proxy engineering phase only',delivery_files_verified=len(manifest['files']),dataset=dataset,
                 model_sha256=model_hash,report_links='PASS',fallback_checks=162,regression_exit_code=result.returncode,
                 regression_log_sha256=hashlib.sha256((output/'unittest.log').read_bytes()).hexdigest(),
                 tests_discovered=tests_discovered,test_run_passed=result.returncode==0)
    (output/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    if result.returncode:raise RuntimeError('targeted regression failed')
    return summary

if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
