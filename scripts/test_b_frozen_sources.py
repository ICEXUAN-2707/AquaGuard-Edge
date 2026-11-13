import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from b_frozen_sources import REQUIRED_SOURCES, source_digests, verify_sources
from b_training_inputs import verify_inputs
ROOT=Path(__file__).resolve().parents[1]

class FrozenSourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for relative in REQUIRED_SOURCES:
            target=self.root/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
        self.manifest=json.loads((ROOT/'deliverables/B-PROXY-INPUTS-001/manifest.json').read_text())
        self.plan=json.loads((ROOT/'deliverables/B-CANDIDATE-PROXY-001/training_plan.lock.json').read_text())
        self.rows=[json.loads(l) for l in (ROOT/'deliverables/B-PROXY-INPUTS-001/features.jsonl').read_text().splitlines()]
    def verify(self,manifest=None):
        return verify_inputs(self.root,manifest or self.manifest,self.plan,self.rows,
                             ROOT/'deliverables/B-SIM-001',ROOT/'deliverables/B-PROXY-INPUTS-001/repaired_split_proposal.json')
    def test_complete_snapshot_passes(self):
        self.assertEqual(self.verify()['cohort_validation'],'PASS')
    def test_missing_rules_rejected(self):
        (self.root/'spikes/SP-04/src/rules.py').unlink()
        with self.assertRaisesRegex(ValueError,'required frozen dependency missing'):self.verify()
    def test_rules_and_gates_tampering_rejected(self):
        for relative in ('spikes/SP-04/src/rules.py','spikes/SP-04/src/gates.py'):
            with self.subTest(relative=relative):
                path=self.root/relative;original=path.read_bytes();path.write_bytes(original+b'\n# changed\n')
                with self.assertRaisesRegex(ValueError,'frozen dependency changed'):self.verify()
                path.write_bytes(original)
    def test_unattended_999_rejected(self):
        p=self.root/'spikes/SP-04/data/rules_config.json';config=json.loads(p.read_text(encoding="utf-8-sig"));config['unattended_sec']=999;p.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError,'frozen dependency changed'):self.verify()
    def test_deleted_manifest_entry_rejected_even_if_disk_file_missing(self):
        manifest=copy.deepcopy(self.manifest)
        del manifest['provenance']['source_files']['spikes/SP-04/src/rules.py']
        (self.root/'spikes/SP-04/src/rules.py').unlink()
        with self.assertRaisesRegex(ValueError,'inventory mismatch'):self.verify(manifest)
    def test_provenance_generation_refuses_missing_dependency(self):
        (self.root/'spikes/SP-04/data/rules_config.json').unlink()
        with self.assertRaisesRegex(ValueError,'required frozen dependency missing'):source_digests(self.root)

    def test_crlf_lf_only_normalization(self):
        expected=source_digests(self.root)
        path=self.root/'spikes/SP-04/data/rules_config.json'
        path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
        self.assertEqual(verify_sources(self.root,expected),expected)

if __name__=='__main__':unittest.main()
