import json
import tempfile
import unittest
from pathlib import Path
from train_b_proxy import ROOT
from experiment.ml import load_model,ModelUnavailable

class ModelLoadTest(unittest.TestCase):
    def test_missing_corrupt_wrong_version(self):
        model=json.loads((ROOT/'deliverables/B-PROXY-MODEL-001/model.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'model.json'
            with self.assertRaises(ModelUnavailable):load_model(p)
            p.write_text('{bad')
            with self.assertRaises(ModelUnavailable):load_model(p)
            model['feature_version']='unsupported'
            p.write_text(json.dumps(model))
            with self.assertRaises(ModelUnavailable):load_model(p)

if __name__=='__main__':unittest.main()
