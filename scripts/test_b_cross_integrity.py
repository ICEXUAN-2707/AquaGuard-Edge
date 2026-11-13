import copy
import json
import unittest
from pathlib import Path
from b_bundle_checks import check_annotations
from b_evidence_checks import check_evidence
from b_training_inputs import verify_inputs
ROOT=Path(__file__).resolve().parents[1]

class CrossIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.rows=[json.loads(l) for l in (ROOT/'deliverables/B-PROXY-INPUTS-001/features.jsonl').read_bytes().splitlines()]
        self.annotations=[json.loads(l) for l in (ROOT/'deliverables/B-CANDIDATE-PROXY-001/labels.jsonl').read_bytes().splitlines()]
        self.records=[json.loads(l) for l in (ROOT/'deliverables/B-PROXY-EVAL-001/predictions.jsonl').read_bytes().splitlines()]
        self.report=json.loads((ROOT/'deliverables/B-PROXY-EVAL-001/report.json').read_text())
        self.fallback=json.loads((ROOT/'deliverables/B-PROXY-FALLBACK-001/fallback_report.json').read_text())
        self.plan=json.loads((ROOT/'deliverables/B-CANDIDATE-PROXY-001/training_plan.lock.json').read_text())
        self.fm=json.loads((ROOT/'deliverables/B-PROXY-INPUTS-001/manifest.json').read_text())
    def check(self):
        return check_evidence(self.records,self.report,self.fallback,self.annotations,self.report['model_sha256'],self.plan['feature_manifest_sha256'])
    def test_existing_evidence_passes(self):
        self.assertEqual(self.check(),162)
    def test_equivalent_timestamp_spellings(self):
        for record in self.fallback['records']:
            record['window_end']=record['window_end'].replace('+00:00','Z')
        self.assertEqual(self.check(),162)
    def test_duplicate_fallback_record_rejected(self):
        self.fallback['records'][-1]=copy.deepcopy(self.fallback['records'][0])
        with self.assertRaisesRegex(ValueError,'fallback inventory'):self.check()
    def test_wrong_model_fallback_rejected(self):
        self.fallback['model_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'model/source'):self.check()
    def test_modified_summary_rejected(self):
        self.report['primary']['C3']['tp']+=1
        with self.assertRaisesRegex(ValueError,'report metrics'):self.check()
    def test_modified_fallback_summary_rejected(self):
        self.fallback['by_variant']['missing']-=1
        with self.assertRaisesRegex(ValueError,'fallback summary'):self.check()
    def test_integer_prediction_rejected(self):
        self.records[0]['methods']['C3']['value']=0
        with self.assertRaisesRegex(ValueError,'prediction type'):self.check()
    def test_duplicate_prediction_rejected(self):
        self.records[-1]=copy.deepcopy(self.records[0])
        with self.assertRaisesRegex(ValueError,'prediction inventory'):self.check()
    def test_integer_target_rejected(self):
        self.annotations[0]['candidate_target']=0
        with self.assertRaisesRegex(ValueError,'boolean or null'):check_annotations(self.rows,self.annotations)
    def test_label_history_binding_rejected(self):
        self.annotations[0]['source_history_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'history binding'):check_annotations(self.rows,self.annotations)
    def test_duplicate_feature_window_rejected(self):
        self.rows[-1]=copy.deepcopy(self.rows[0])
        with self.assertRaisesRegex(ValueError,'window inventory'):verify_inputs(ROOT,self.fm,self.plan,self.rows)
    def test_future_publication_rejected(self):
        self.rows[0]['published_at']='2026-11-10T00:01:32+00:00'
        with self.assertRaisesRegex(ValueError,'publication time'):verify_inputs(ROOT,self.fm,self.plan,self.rows)
    def test_nonfinite_feature_rejected(self):
        self.rows[0]['features']['flow_mean_lpm']=float('nan')
        with self.assertRaisesRegex(ValueError,'invalid feature'):verify_inputs(ROOT,self.fm,self.plan,self.rows)

if __name__=='__main__':unittest.main()
