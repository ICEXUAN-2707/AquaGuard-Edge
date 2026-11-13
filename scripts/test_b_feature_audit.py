import unittest
from b_feature_audit import validate_split

class SplitProtectionTest(unittest.TestCase):
    def test_reject_duplicate_missing_and_cohort_leakage(self):
        trials=[dict(trial_id='a',cohort_id='g'),dict(trial_id='b',cohort_id='g')]
        for mapping in ({'train':['a'],'validation':['a','b'],'test':[]}, {'train':['a'],'validation':[],'test':[]}, {'train':['a'],'validation':['b'],'test':[]}):
            with self.assertRaises(ValueError):validate_split({'trials':mapping},trials)
        self.assertEqual(validate_split({'trials':{'train':['a','b'],'validation':[],'test':[]}},trials),{'a':'train','b':'train'})

if __name__=='__main__':unittest.main()
