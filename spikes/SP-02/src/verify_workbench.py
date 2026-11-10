"""Owned local broker -> SP-02 journal -> public edge API integration check."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))


def wait(check, timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            result=check()
            if result: return result
        except (OSError,ValueError): pass
        time.sleep(.1)
    raise TimeoutError('integration readiness timeout')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--broker',type=Path,required=True)
    parser.add_argument('--mqtt-port',type=int,default=18886)
    parser.add_argument('--http-port',type=int,default=8021)
    parser.add_argument('--browser',action='store_true',help='verify browser and ACK in the same MQTT run')
    args=parser.parse_args()
    args.directory=args.directory.resolve()
    for port in (args.mqtt_port,args.http_port):
        with socket.socket() as probe: probe.bind(('127.0.0.1',port))
    args.directory.mkdir(parents=True,exist_ok=False)
    config=args.directory/'broker.conf'
    config.write_text(f'listener {args.mqtt_port} 127.0.0.1\nallow_anonymous true\npersistence false\n')
    processes=[]; logs=[]; token=uuid4().hex
    def launch(command,name,env=None):
        log=(args.directory/(name+'.log')).open('w');logs.append(log)
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log)
        processes.append(process);return process
    def request(route):
        req=urllib.request.Request(f'http://127.0.0.1:{args.http_port}'+route,headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
    try:
        launch([str(args.broker),'-c',str(config)],'broker')
        def listening():
            with socket.socket() as sock:return sock.connect_ex(('127.0.0.1',args.mqtt_port))==0
        wait(listening)
        cli=Path(__file__).with_name('cli.py')
        launch([sys.executable,str(cli),'subscribe','--device-id','demo01','--directory',str(args.directory),
                '--port',str(args.mqtt_port),'--seconds','90'],'subscriber')
        wait(lambda:'READY' in (args.directory/'subscriber.log').read_text())
        from core import Journal
        Journal(args.directory/'journal.sqlite').close()
        env=os.environ.copy()
        env.update(AQUAGUARD_RUNTIME='mqtt',AQUAGUARD_DEVICE_ID='demo01',AQUAGUARD_PORT=str(args.http_port),
            AQUAGUARD_DB=str(args.directory/'business.sqlite'),AQUAGUARD_MQTT_JOURNAL=str(args.directory/'journal.sqlite'),
            AQUAGUARD_C_TOKEN=token,AQUAGUARD_C_CURSOR_KEY=uuid4().hex+uuid4().hex)
        launch([sys.executable,'-m','edge'],'edge',env)
        wait(lambda:request('/health')['status']=='ok')
        from core import sample
        rows=[]
        boot=uuid4().hex
        for i in range(45):
            for sensor in ('flow','water','presence'):
                row=sample(i,sensor,boot,device_id='demo01')
                if sensor=='water':row['value']['wet']=i>=35
                rows.append(row)
        (args.directory/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        publisher=launch([sys.executable,str(cli),'publish','--device-id','demo01','--directory',str(args.directory),
            '--port',str(args.mqtt_port),'--interval','0.34'],'publisher')
        if args.browser:
            browser_env=env.copy()
            browser_env.update(AQUAGUARD_BROWSER_URL=f'http://127.0.0.1:{args.http_port}/c.html',
                AQUAGUARD_BROWSER_TRIAL='mqtt-trial',
                AQUAGUARD_BROWSER_EVIDENCE=str(args.directory/'browser'))
            subprocess.run(['node',str(ROOT/'web/tests/browser-acceptance.cjs')],cwd=ROOT,
                           env=browser_env,check=True,timeout=150)
        assert publisher.wait(timeout=65)==0
        live=wait(lambda:request('/api/devices/demo01/live'))
        events=wait(lambda:request('/api/events?device_id=demo01')['items'])
        assert live['origin']=='simulation'
        assert any(e['event_type']=='WATER_CONTACT' for e in events)
        if args.browser:
            assert any(e['event_type']=='WATER_CONTACT' and e['ack_status']=='ACKNOWLEDGED' for e in events)
        (args.directory/'events.json').write_text(json.dumps(events,indent=2))
        sync=request('/api/sync/status?device_id=demo01')
        assert sync['pending_count']>0
        trial=request('/api/experiments/mqtt-trial')
        assert trial['asset_refs']
        result=dict(status='PASS',origin=live['origin'],event_types=[e['event_type'] for e in events],
                    pending_count=sync['pending_count'],trial_id=trial['trial_id'],cloud_connected=False)
        (args.directory/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:
        for process in reversed(processes):
            if process.poll() is None:process.terminate();process.wait(timeout=10)
        for log in logs:log.close()


if __name__=='__main__':main()
