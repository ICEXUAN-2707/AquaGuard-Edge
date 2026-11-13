import tempfile
import unittest
from pathlib import Path
from train_b_proxy import run,checked
ROOT=Path(__file__).resolve().parents[1]

class TrainingTest(unittest.TestCase):
    def test_reproducible_model_and_no_test_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            result=run(ROOT/'deliverables/B-PROXY-INPUTS-001',ROOT/'deliverables/B-CANDIDATE-PROXY-001',Path(folder)/'model')
            import json
            previous=json.loads((ROOT/'deliverables/B-PROXY-MODEL-001/model.lock.json').read_text())
            self.assertEqual(result['model_sha256'],previous['model_sha256'])
            self.assertFalse(result['test_evaluated'])
            self.assertEqual(result['selected']['hyperparameters']['max_depth'],1)
    def test_digest_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'artifact';p.write_bytes(b'changed')
            with self.assertRaises(ValueError):checked(p,'0'*64)

if __name__=='__main__':unittest.main()
