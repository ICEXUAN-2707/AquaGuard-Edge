import unittest
from publish_b_proxy_labels import label

class ProxyLabelTest(unittest.TestCase):
    def test_causal_proxy_and_unknown(self):
        row={'features':{'flow_active_ratio':1,'absence_after_flow_sec':10},'rejection_reasons':[]}
        self.assertTrue(label(row)[0])
        self.assertEqual(label(dict(row,original_episode_target=False)),label(dict(row,original_episode_target=True)))
        self.assertIsNone(label(dict(row,rejection_reasons=['PRESENCE_STATE_UNKNOWN']))[0])
        self.assertFalse(label(dict(row,features={'flow_active_ratio':0,'absence_after_flow_sec':10}))[0])
        self.assertFalse(label(dict(row,features={'flow_active_ratio':1,'absence_after_flow_sec':9}))[0])

if __name__=='__main__':unittest.main()
