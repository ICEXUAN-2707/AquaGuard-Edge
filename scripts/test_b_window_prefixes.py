import unittest
from datetime import datetime, timezone
from audit_b_window_prefixes import fingerprint

class PrefixTest(unittest.TestCase):
    def test_future_and_identity_invariance(self):
        end=datetime(2026,11,10,0,0,30,tzinfo=timezone.utc)
        row=dict(sensor_type='presence',seq=1,event_time='2026-11-10T00:00:20+00:00',received_at='2026-11-10T00:00:20+00:00',value={'present':False},device_id='a')
        base=fingerprint([row],end)
        self.assertEqual(base,fingerprint([dict(row,device_id='b')],end))
        self.assertEqual(base,fingerprint([row,dict(row,seq=2,received_at='2026-11-10T00:00:31+00:00')],end))
        self.assertEqual(base,fingerprint([row,dict(row,seq=2,event_time='2026-11-10T00:00:31+00:00')],end))
        self.assertNotEqual(base,fingerprint([dict(row,value={'present':True})],end))

if __name__=='__main__':unittest.main()
