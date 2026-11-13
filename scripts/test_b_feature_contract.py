import unittest
from audit_b_feature_proximity import distance,SCALES
from extract_b_expanded_features import feature_vector,MODEL_FEATURE_NAMES

class FeatureContractTest(unittest.TestCase):
    def test_allowlist_and_invalid_values(self):
        values={n:1.0 for n in MODEL_FEATURE_NAMES}
        self.assertEqual(set(feature_vector(dict(values,trial_id='secret',water_contact=True))),set(MODEL_FEATURE_NAMES))
        for value in (None,float('nan'),float('inf')):
            self.assertIsNone(feature_vector(dict(values,flow_mean_lpm=value)))
    def test_fixed_proximity(self):
        a={k:0.0 for k in SCALES};b=dict(a,flow_mean_lpm=.04)
        self.assertAlmostEqual(distance(a,b),.04)
        self.assertEqual(distance(a,a),0)
        self.assertIsNone(distance(a,dict(a,flow_streak_sec=None)))
        with self.assertRaises(ValueError):distance(dict(a,scenario='idle'),b)

if __name__=='__main__':unittest.main()
