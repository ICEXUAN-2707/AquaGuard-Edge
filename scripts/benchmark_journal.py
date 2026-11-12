"""Offline Journal insertion scaling probe, not MQTT throughput acceptance."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'spikes/SP-02/src'))
from core import Journal, normalize, sample


def run(directory,counts):
    directory.mkdir(parents=True,exist_ok=False)
    results=[]
    for count in counts:
        path=directory/f'journal-{count}.sqlite'
        journal=Journal(path);boot=uuid4().hex;latencies=[]
        try:
            for i in range(count):
                wire=sample(i,['flow','water','presence'][i%3],boot,device_id='demo01')
                row=normalize(json.dumps(wire),'demo01','simulation')
                start=time.perf_counter();journal.accept(row);latencies.append(time.perf_counter()-start)
        finally:journal.close()
        tail=latencies[-min(100,count):]
        results.append(dict(observations=count,sqlite_bytes=path.stat().st_size,
                            insertion_seconds=sum(latencies),tail_samples=len(tail),
                            tail_mean_ms=statistics.mean(tail)*1000,tail_max_ms=max(tail)*1000))
    report=dict(scope='offline_single_process_journal_insertion',results=results,
                note='Includes SQLite commits; excludes MQTT, ACK, subscriber and edge consumer. Host may have concurrent observation load; not an isolated benchmark, complexity proof or production throughput guarantee.')
    (directory/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--counts',type=int,nargs='+',default=[300,600,1200])
    args=parser.parse_args()
    if any(n<1 for n in args.counts) or len(set(args.counts))!=len(args.counts):parser.error('Unique positive counts required')
    print(json.dumps(run(args.directory,args.counts)))


if __name__=='__main__':main()
