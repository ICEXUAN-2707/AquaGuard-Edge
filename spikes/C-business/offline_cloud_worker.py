"""Explicit IoTDA mapping/worker assembly with a network-free failure transport."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.base import RetryableFailure, PermanentFailure
from adapters.iotda import IoTDAAdapter
from cloud_config import load_config, ConfigError
from delivery import DeliveryService
from outbox import Worker


class OfflineTransport:
    def __init__(self,mode='retry'):
        if mode not in ('retry','permanent'):raise ValueError('offline failure mode required')
        self.mode=mode;self.closed=False;self.calls=0
    def send(self,payload,*,message_id,attempt_token):
        if self.closed:raise RuntimeError('offline transport closed')
        self.calls+=1
        # No socket/client construction and no fabricated cloud acceptance.
        return RetryableFailure('OFFLINE_NO_NETWORK') if self.mode=='retry' else PermanentFailure('OFFLINE_REJECTED')
    def close(self):self.closed=True


def utcnow():return datetime.now(timezone.utc).isoformat()


def assemble(path,config,*,mode='retry',clock=utcnow):
    if not Path(path).is_file():raise ValueError('existing isolated business database required')
    if not config.bindings or any(b.authorization_class!='simulation_test' or b.allowed_origins!=('simulation',) for b in config.bindings):
        raise ConfigError('offline worker requires simulation-only test bindings')
    transport=OfflineTransport(mode)
    return DeliveryService(Worker(path),IoTDAAdapter(config,transport),finish_clock=clock)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--mode',choices=('retry','permanent'),default='retry')
    parser.add_argument('--steps',type=int,default=1)
    args=parser.parse_args()
    if not 1<=args.steps<=100:parser.error('steps must be 1..100')
    service=assemble(args.db,load_config(),mode=args.mode)
    try:
        statuses=[service.step(now=utcnow()) for _ in range(args.steps)]
        print(json.dumps({'scope':'offline_mapping_worker','network_enabled':False,'cloud_accepted':False,'statuses':statuses}))
    finally:service.close()


if __name__=='__main__':main()
