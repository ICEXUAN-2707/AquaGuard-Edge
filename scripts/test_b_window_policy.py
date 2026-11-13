import unittest
from datetime import datetime, timedelta
from extract_b_expanded_features import CONFIG
from alignment import align
from engine import compute
from build_b_sim_dataset import generate_trial, START

class WindowPolicyTest(unittest.TestCase):
    def test_delayed_endpoint_and_future_filter(self):
        config=dict(cadence_sec=5,receive_delay_sec=.3,flow_lpm=1.2,leave_at=10,brief_leave_at=24,brief_duration=5)
        rows=generate_trial('test-b-window','unattended',config)
        end=START+timedelta(seconds=30)
        def window(wait, rows):
            history=[r for r in rows if datetime.fromisoformat(r['received_at'])<=end+timedelta(seconds=wait) and datetime.fromisoformat(r['event_time'])<=end]
            cfg=dict(CONFIG,lateness=wait)
            w=align(history,[end],**cfg)['windows'][0]
            return w,compute(w,history,alignment_config=cfg)['features']
        self.assertEqual(window(0,rows)[0]['sensor_summary']['flow']['state'],'unknown')
        fixed=window(2,rows)
        self.assertEqual(fixed[0]['sensor_summary']['flow']['state'],'active')
        prefix=[r for r in rows if datetime.fromisoformat(r['event_time'])<=end]
        self.assertEqual(fixed,window(2,prefix))
    def test_missing_cadence_endpoint_remains_unknown(self):
        config=dict(cadence_sec=2,receive_delay_sec=.3,flow_lpm=1.2,leave_at=10,brief_leave_at=24,brief_duration=5)
        rows=generate_trial('test-b-cadence','unattended',config)
        end=START+timedelta(seconds=35)
        history=[r for r in rows if datetime.fromisoformat(r['event_time'])<=end]
        self.assertEqual(align(history,[end],**CONFIG)['windows'][0]['sensor_summary']['flow']['state'],'unknown')

if __name__=='__main__': unittest.main()
