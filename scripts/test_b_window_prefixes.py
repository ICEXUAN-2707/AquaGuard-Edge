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

    def test_publication_wait_accepts_arrival_but_never_future_event(self):
        end=datetime(2026,11,10,0,0,30,tzinfo=timezone.utc)
        row=dict(sensor_type='flow',seq=1,event_time='2026-11-10T00:00:30+00:00',received_at='2026-11-10T00:00:30.3+00:00',value={'estimated_lpm':1.0})
        self.assertEqual(fingerprint([row],end),fingerprint([],end))
        self.assertNotEqual(fingerprint([row],end,lateness=2),fingerprint([],end,lateness=2))
        future=dict(row,event_time='2026-11-10T00:00:31+00:00')
        self.assertEqual(fingerprint([future],end,lateness=2),fingerprint([],end,lateness=2))

if __name__=='__main__':unittest.main()
