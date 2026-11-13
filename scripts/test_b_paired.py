import unittest
from compare_b_paired import compare,required_pairs

def row(target,c2,c3):return {'target':target,'methods':{'C2':{'value':c2},'C3':{'value':c3}}}

class PairedTest(unittest.TestCase):
    def test_paired_sign_and_refused_positive(self):
        r=compare([row(False,True,False),row(True,None,True),row(None,None,None)])
        self.assertEqual(r['false_positive']['benefit'],1)
        self.assertEqual(r['miss_including_refusal']['benefit'],1)
        self.assertEqual(r['refusal_all']['benefit'],1/3)
    def test_ties_and_empty(self):
        self.assertEqual(compare([row(False,False,False)])['false_positive']['benefit'],0)
        self.assertIsNone(compare([])['false_positive']['benefit'])
    def test_planning_monotone(self):
        self.assertGreater(required_pairs(.1,.05,.3),required_pairs(.1,.05,.12))
        with self.assertRaises(ValueError):required_pairs(.05,.05,.2)

if __name__=='__main__':unittest.main()
