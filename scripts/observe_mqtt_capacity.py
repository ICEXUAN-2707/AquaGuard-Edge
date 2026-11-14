"""Bounded read-only capacity sampling; no broker, publisher, worker or network."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from mqtt_capacity_snapshot import snapshot

def collect(journal,business,output,*,samples=1,interval=15,allow_long_run=False):
    if type(samples) is not int or not 1<=samples<=10000 or not 1<=interval<=3600:
        raise ValueError('bounded samples and interval required')
    if (samples-1)*interval>60 and not allow_long_run:
        raise ValueError('long collection is disabled without explicit allow_long_run')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();count=0;error=None
    try:
        with (output/'samples.jsonl').open('w',encoding='utf-8') as stream:
            for number in range(samples):
                value={'utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-started,
                       **snapshot(journal,business)}
                stream.write(json.dumps(value)+'\n');stream.flush();count+=1
                if number+1<samples:time.sleep(interval)
    except BaseException as exc:error=type(exc).__name__
    result={'scope':'inventory_collection_only','collection_status':'COMPLETED' if error is None and count==samples else 'INCOMPLETE',
            'requested_samples':samples,'recorded_samples':count,'error_type':error,
            'long_run_acceptance':False,'note':'Collection completion is not MQTT availability, throughput, ACK latency or long-duration acceptance.'}
    (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('journal','db','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--samples',type=int,default=1);parser.add_argument('--interval',type=float,default=15)
    parser.add_argument('--allow-long-run',action='store_true')
    args=parser.parse_args()
    value=collect(args.journal,args.db,args.output,samples=args.samples,interval=args.interval,allow_long_run=args.allow_long_run)
    print(json.dumps(value));raise SystemExit(0 if value['collection_status']=='COMPLETED' else 1)
