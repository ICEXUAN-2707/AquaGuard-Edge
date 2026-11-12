"""Owned local broker -> SP-02 journal -> public edge API integration check."""
import argparse
import json
import hashlib
import os
import platform
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
    parser.add_argument('--lifecycle',action='store_true',help='include dry, browser close and recurrence')
    parser.add_argument('--recovery',action='store_true',help='real expiry, edge restart and new MQTT boot')
    parser.add_argument('--evaluation-report',type=Path)
    args=parser.parse_args()
    if args.lifecycle: args.browser=True
    if args.recovery and (args.browser or args.lifecycle): parser.error('recovery is a separate scenario')
    args.directory=args.directory.resolve()
    for port in (args.mqtt_port,args.http_port):
        with socket.socket() as probe: probe.bind(('127.0.0.1',port))
    args.directory.mkdir(parents=True,exist_ok=False)
    config=args.directory/'broker.conf'
    config.write_text(f'listener {args.mqtt_port} 127.0.0.1\nallow_anonymous true\npersistence false\n')
    processes=[]; logs=[]; token=uuid4().hex
    started=time.monotonic()
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip())
    (args.directory/'run.json').write_text(json.dumps(dict(revision=revision,tracked_changes=dirty,
        python=sys.version,platform=platform.platform(),source='simulation',runtime='mqtt',
        mqtt_port=args.mqtt_port,http_port=args.http_port,recovery=args.recovery,
        lifecycle=args.lifecycle,browser=args.browser or args.recovery),indent=2))
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
                '--port',str(args.mqtt_port),'--seconds','180'],'subscriber')
        wait(lambda:'READY' in (args.directory/'subscriber.log').read_text())
        from core import Journal
        Journal(args.directory/'journal.sqlite').close()
        env=os.environ.copy()
        env.update(AQUAGUARD_RUNTIME='mqtt',AQUAGUARD_DEVICE_ID='demo01',AQUAGUARD_PORT=str(args.http_port),
            AQUAGUARD_DB=str(args.directory/'business.sqlite'),AQUAGUARD_MQTT_JOURNAL=str(args.directory/'journal.sqlite'),
            AQUAGUARD_C_TOKEN=token,AQUAGUARD_C_CURSOR_KEY=uuid4().hex+uuid4().hex)
        edge=launch([sys.executable,'-m','edge'],'edge',env)
        wait(lambda:request('/health')['status']=='ok')
        from core import sample
        rows=[]
        boot=uuid4().hex
        for i in range(65 if args.lifecycle else 45):
            for sensor in ('flow','water','presence'):
                row=sample(i,sensor,boot,device_id='demo01')
                if sensor=='water':row['value']['wet']=(35<=i<42 or i>=58) if args.lifecycle else i>=35
                rows.append(row)
        (args.directory/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        publisher=launch([sys.executable,str(cli),'publish','--device-id','demo01','--directory',str(args.directory),
            '--port',str(args.mqtt_port),'--interval','0.34'],'publisher')
        if args.recovery:
            browser_env=env.copy()
            browser_env.update(AQUAGUARD_BROWSER_URL=f'http://127.0.0.1:{args.http_port}/c.html',
                AQUAGUARD_BROWSER_EVIDENCE=str(args.directory/'browser'))
            browser=launch(['node',str(ROOT/'web/tests/browser-recovery.cjs')],'browser',browser_env)
            assert publisher.wait(timeout=90)==0
            # No publisher runs during this gap. Let actual TTL and UI polling expire.
            time.sleep(18)
            before=request('/api/events?device_id=demo01')['items']
            water=[e for e in before if e['event_type']=='WATER_CONTACT']
            assert len(water)==1 and water[0]['physical_status']=='UNKNOWN'
            edge.terminate();edge.wait(timeout=10)
            edge=launch([sys.executable,'-m','edge'],'edge-restarted',env)
            wait(lambda:request('/health')['status']=='ok')
            second=args.directory/'second-boot';second.mkdir()
            boot2=uuid4().hex
            rows2=[]
            for i in range(45):
                for sensor in ('flow','water','presence'):
                    row=sample(i,sensor,boot2,device_id='demo01')
                    if sensor=='water':row['value']['wet']=True
                    rows2.append(row)
            (second/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows2))
            publisher=launch([sys.executable,str(cli),'publish','--device-id','demo01','--directory',str(second),
                '--port',str(args.mqtt_port),'--interval','0.34'],'publisher-second')
            assert publisher.wait(timeout=90)==0
            assert browser.wait(timeout=45)==0
            after=request('/api/events?device_id=demo01')['items']
            resumed=[e for e in after if e['event_type']=='WATER_CONTACT']
            assert len(resumed)==1 and resumed[0]['event_id']==water[0]['event_id']
            assert resumed[0]['physical_status']=='ACTIVE'
            (args.directory/'recovery.json').write_text(json.dumps(dict(status='PASS',
                event_id=resumed[0]['event_id'],before=water[0],after=resumed[0],
                first_boot=boot,second_boot=boot2,cloud_connected=False),indent=2))
        if args.browser:
            if args.evaluation_report:
                wait(lambda:request('/api/experiments/mqtt-trial'),timeout=50)
                subprocess.run([sys.executable,str(ROOT/'spikes/C-business/evaluations.py'),
                    '--db',str(args.directory/'business.sqlite'),'--root',str(ROOT),
                    '--report',str(args.evaluation_report.resolve()),'--evaluation-id','rules-r07',
                    '--experiment-id','mqtt-trial'],cwd=ROOT,env=env,check=True)
                env['AQUAGUARD_BROWSER_EVALUATION']='rules-r07'
            browser_env=env.copy()
            browser_env.update(AQUAGUARD_BROWSER_URL=f'http://127.0.0.1:{args.http_port}/c.html',
                AQUAGUARD_BROWSER_TRIAL='mqtt-trial',
                AQUAGUARD_BROWSER_LIFECYCLE='1' if args.lifecycle else '0',
                AQUAGUARD_BROWSER_EVIDENCE=str(args.directory/'browser'))
            subprocess.run(['node',str(ROOT/'web/tests/browser-acceptance.cjs')],cwd=ROOT,
                           env=browser_env,check=True,timeout=150)
        assert publisher.wait(timeout=90)==0
        live=wait(lambda:request('/api/devices/demo01/live'))
        events=wait(lambda:request('/api/events?device_id=demo01')['items'])
        assert live['origin']=='simulation'
        assert any(e['event_type']=='WATER_CONTACT' for e in events)
        if args.browser:
            assert any(e['event_type']=='WATER_CONTACT' and e['ack_status']=='ACKNOWLEDGED' for e in events)
        if args.lifecycle:
            assert any(e['event_type']=='WATER_CONTACT' and e['lifecycle']=='CLOSED' for e in events)
            assert any(e['event_type']=='WATER_CONTACT' and e['lifecycle']=='OPEN' and e['ack_status']=='UNACKNOWLEDGED' for e in events)
        (args.directory/'events.json').write_text(json.dumps(events,indent=2))
        sync=request('/api/sync/status?device_id=demo01')
        assert sync['pending_count']>0
        trial=request('/api/experiments/mqtt-trial')
        assert trial['asset_refs']
        result=dict(status='PASS',origin=live['origin'],event_types=[e['event_type'] for e in events],
                    pending_count=sync['pending_count'],trial_id=trial['trial_id'],cloud_connected=False,
                    revision=revision,tracked_changes=dirty,duration_seconds=time.monotonic()-started,
                    manifest_sha256=hashlib.sha256((args.directory/'manifest.jsonl').read_bytes()).hexdigest())
        (args.directory/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    except BaseException as exc:
        (args.directory/'result.json').write_text(json.dumps(dict(status='FAIL',error_type=type(exc).__name__,
            revision=revision,cloud_connected=False),indent=2))
        raise
    finally:
        cleanup=[]
        for process in reversed(processes):
            try:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait(timeout=5)
                cleanup.append(dict(pid=process.pid,exitcode=process.returncode,exit_confirmed=process.poll() is not None))
            except (OSError,subprocess.TimeoutExpired):
                cleanup.append(dict(pid=process.pid,exit_confirmed=False))
        for log in logs:log.close()
        (args.directory/'cleanup.json').write_text(json.dumps(cleanup,indent=2))
        if not all(item['exit_confirmed'] for item in cleanup):
            raise RuntimeError('owned process exit unconfirmed; inspect cleanup.json')


if __name__=='__main__':main()
