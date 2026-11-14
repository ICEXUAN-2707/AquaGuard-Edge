"""Bounded read-only capacity sampling; no broker, publisher, worker or network."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import math
from mqtt_capacity_snapshot import snapshot

def collect(journal,business,output,*,samples=1,interval=15,allow_long_run=False):
    if type(samples) is not int or not 1<=samples<=10000 or type(interval) not in (int,float) or not math.isfinite(interval) or not 1<=interval<=3600:
        raise ValueError('bounded samples and interval required')
    if (samples-1)*interval>60 and not allow_long_run:
        raise ValueError('long collection is disabled without explicit allow_long_run')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();wall_started=time.time();count=0;error=None
    previous=None;max_gap=None;max_duration=0;max_clock_delta=0;late=0
    try:
        with (output/'samples.jsonl').open('w',encoding='utf-8') as stream:
            for number in range(samples):
                observed=time.monotonic();wall=time.time()
                gap=None if previous is None else observed-previous
                lateness=max(0,observed-(started+number*interval))
                clock_delta=(wall-wall_started)-(observed-started)
                inventory=snapshot(journal,business)
                duration=time.monotonic()-observed
                value={'utc':datetime.fromtimestamp(wall,timezone.utc).isoformat(),'sample_number':number,
                       'elapsed_seconds':observed-started,'sample_gap_seconds':gap,
                       'schedule_lateness_seconds':lateness,'collection_seconds':duration,
                       'wall_minus_monotonic_seconds':clock_delta,
                       'estimated_suspend_seconds':None,**inventory}
                stream.write(json.dumps(value)+'\n');stream.flush();count+=1
                if gap is not None:max_gap=max(max_gap or 0,gap)
                max_duration=max(max_duration,duration);max_clock_delta=max(max_clock_delta,abs(clock_delta))
                if lateness>interval:late+=1
                previous=observed
                if number+1<samples:
                    # Never backfill missed samples in a burst after a host pause.
                    time.sleep(max(interval,started+(number+1)*interval-time.monotonic()))
    except BaseException as exc:error=type(exc).__name__
    result={'scope':'inventory_collection_only','collection_status':'COMPLETED' if error is None and count==samples else 'INCOMPLETE',
            'requested_samples':samples,'recorded_samples':count,'error_type':error,
            'interval_seconds':interval,'max_sample_gap_seconds':max_gap,
            'max_collection_seconds':max_duration,'late_samples':late,
            'max_abs_wall_minus_monotonic_seconds':max_clock_delta,
            'coverage_status':'UNKNOWN' if count<2 else ('GAPS' if late or max_gap>interval*1.5 else 'OBSERVED'),
            'long_run_acceptance':False,'note':'Collection completion is not MQTT availability, throughput, ACK latency or long-duration acceptance. Clock divergence is not a suspend diagnosis; OS suspend metrics are unavailable.'}
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
