import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_b_sim_split import repair

class RepairTest(unittest.TestCase):
    def test_split_and_immutable_parent(self):
        import hashlib
        source = Path(__file__).resolve().parents[1] / 'deliverables/B-SIM-001'
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'repair'
            result = repair(source, output)
            self.assertEqual([len(result['trials'][s]) for s in ('train','validation','test')], [36,18,18])
            self.assertEqual(len(set(sum(result['trials'].values(), []))), 72)
            self.assertFalse(result['training_ready'])
            with self.assertRaises(FileExistsError):
                repair(source, output)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()})

if __name__ == '__main__':
    unittest.main()
