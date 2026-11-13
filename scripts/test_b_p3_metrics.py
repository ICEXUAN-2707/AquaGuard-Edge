import unittest
from evaluate_b_proxy import metrics

def row(target,prediction):return {'target':target,'methods':{'C3':{'value':prediction}}}

class MetricsTest(unittest.TestCase):
    def test_refused_positive_stays_in_recall_denominator(self):
        m=metrics([row(True,True),row(True,None),row(False,True),row(False,None),row(None,True)],'C3')
        self.assertEqual(m['recall'],.5)
        self.assertEqual(m['false_positive_rate'],.5)
        self.assertEqual(m['rejection_rate_known'],.5)
        self.assertEqual(m['unknown_positive_outputs'],1)
    def test_empty_no_positive_no_negative_all_unknown(self):
        for records in ([],[row(None,None)]):
            m=metrics(records,'C3')
            self.assertIsNone(m['recall']);self.assertIsNone(m['false_positive_rate'])
        self.assertIsNone(metrics([row(False,False)],'C3')['recall'])
        self.assertIsNone(metrics([row(True,True)],'C3')['false_positive_rate'])
    def test_all_refused_known(self):
        m=metrics([row(True,None),row(False,None)],'C3')
        self.assertEqual(m['recall'],0)
        self.assertEqual(m['rejection_rate_known'],1)
        self.assertEqual(m['rejection_rate_all'],1)

if __name__=='__main__':unittest.main()
