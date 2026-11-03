"""One-command software gate; runs real Broker scenarios, no hardware access."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker',required=True)
    parser.add_argument('--directory',type=Path,required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True,exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    src = Path(__file__).parent
    commands = [
        [sys.executable,'-m','pytest','spikes/SP-02/tests/unit','tests/contracts','tests/smoke','-q','-p','no:cacheprovider'],
        [sys.executable,str(src/'verify_mqtt.py'),'--broker',args.broker,'--directory',str(args.directory/'mqtt')],
        [sys.executable,str(src/'verify_crash.py'),'--broker',args.broker,'--directory',str(args.directory/'crash')],
    ]
    results = []
    for index, command in enumerate(commands):
        result = subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=120)
        (args.directory/f'gate-{index}.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        results.append(dict(gate=index,returncode=result.returncode))
        if result.returncode:
            break
    summary = dict(status='PASS' if len(results)==3 and all(r['returncode']==0 for r in results) else 'FAIL',gates=results)
    (args.directory/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary))
    raise SystemExit(0 if summary['status']=='PASS' else 1)


if __name__ == '__main__':
    main()
