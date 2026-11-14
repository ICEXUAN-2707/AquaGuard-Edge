import importlib.util
import json
import sys
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('supervision',Path(__file__).resolve().parents[2]/'scripts/supervise_endurance.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_atomic_receipt_replaces_prior_state_and_leaves_no_partial_file(tmp_path):
    path=tmp_path/'receipt.json'
    module.atomic_json(path,{'phase':'running'})
    module.atomic_json(path,{'phase':'failed','child_exit_code':1})
    assert json.loads(path.read_text())=={'phase':'failed','child_exit_code':1}
    assert not path.with_suffix('.json.tmp').exists()

def test_failed_child_is_not_mislabeled_completed(tmp_path,monkeypatch):
    output=tmp_path/'new-observation'
    script=tmp_path/'child.py';script.write_text('pass')
    monkeypatch.setattr(sys,'argv',['supervise','--directory',str(output),'--script',str(script),'--seconds','60'])
    monkeypatch.setattr(module,'owned_process_job',lambda:None)
    class FailedChild:
        pid=123
        returncode=7
        def wait(self,timeout):return self.returncode
        def poll(self):return self.returncode
    monkeypatch.setattr(module.subprocess,'Popen',lambda *args,**kwargs:FailedChild())
    assert module.main()==1
    receipt=json.loads((tmp_path/'new-observation.supervisor.json').read_text())
    assert receipt['phase']=='failed' and receipt['child_exit_code']==7
    assert receipt['acceptance_passed'] is False and receipt['child_exit_confirmed'] is True


def test_real_short_child_preserves_argument_boundaries_without_acceptance(tmp_path,monkeypatch):
    output=tmp_path/'short';script=tmp_path/'child with space.py'
    script.write_text('import sys; assert sys.argv[1:] == ["two words", "--flag"]; print("child finished")')
    monkeypatch.setattr(sys,'argv',['supervise','--directory',str(output),'--script',str(script),'--seconds','5','--','two words','--flag'])
    monkeypatch.setattr(module,'owned_process_job',lambda:None)
    assert module.main()==0
    receipt=json.loads((tmp_path/'short.supervisor.json').read_text())
    assert receipt['phase']=='completed' and receipt['child_exit_confirmed']
    assert not receipt['acceptance_passed']
    assert 'child finished' in (tmp_path/'short.supervisor.log').read_text()


def test_long_execution_is_rejected_before_creating_output(tmp_path,monkeypatch):
    script=tmp_path/'child.py';script.write_text('pass')
    monkeypatch.setattr(sys,'argv',['supervise','--directory',str(tmp_path/'long'),'--script',str(script),'--seconds','3600'])
    with pytest.raises(SystemExit) as exc:module.main()
    assert exc.value.code==2 and not (tmp_path/'long').exists()
    assert not (tmp_path/'long.supervisor.json').exists()


def test_taskkill_start_failure_still_records_cleanup(tmp_path,monkeypatch):
    script=tmp_path/'child.py';script.write_text('pass');output=tmp_path/'timeout'
    monkeypatch.setattr(sys,'argv',['supervise','--directory',str(output),'--script',str(script),'--seconds','1'])
    monkeypatch.setattr(module,'owned_process_job',lambda:None)
    ticks=iter([0,2,2]);monkeypatch.setattr(module.time,'monotonic',lambda:next(ticks))
    class Child:
        pid=123;returncode=None
        def poll(self):return self.returncode
        def kill(self):self.returncode=-9
        def terminate(self):raise OSError('cannot start cleanup')
        def wait(self,timeout):return self.returncode
    monkeypatch.setattr(module.subprocess,'Popen',lambda *args,**kwargs:Child())
    def fail(*args,**kwargs):raise OSError('taskkill could not start')
    monkeypatch.setattr(module.subprocess,'run',fail)
    assert module.main()==1
    receipt=json.loads((tmp_path/'timeout.supervisor.json').read_text())
    assert receipt['phase']=='supervisor_error' and receipt['error_type']=='TimeoutError'
    assert receipt['cleanup_error_type']=='OSError' and receipt['child_exit_confirmed']
    assert receipt['child_exit_code']==-9


def test_scheduler_default_preview_never_registers_or_starts(tmp_path):
    import os
    import subprocess
    if os.name!='nt':pytest.skip('Windows scheduled-task preview')
    script=tmp_path/'child.py';script.write_text('pass')
    entry=Path(__file__).resolve().parents[2]/'scripts/start_endurance_task.ps1'
    pythonw=Path(sys.executable).with_name('pythonw.exe')
    output=tmp_path/'preview'
    # Sentinels fail the test if preview touches any Task Scheduler command.
    shell="function New-ScheduledTaskAction { throw 'unexpected task action' }; function Register-ScheduledTask { throw 'unexpected registration' }; function Start-ScheduledTask { throw 'unexpected start' }; & $args[0] -Directory $args[1] -Pythonw $args[2] -Script $args[3]"
    # Powershell -Command args are reparsed; use stdin JSON to preserve paths.
    shell="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $p=[Console]::In.ReadToEnd()|ConvertFrom-Json; "+shell.replace('$args[0]','$p.entry').replace('$args[1]','$p.output').replace('$args[2]','$p.pythonw').replace('$args[3]','$p.script')
    value=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',shell],input=json.dumps(dict(entry=str(entry),output=str(output),pythonw=str(pythonw),script=str(script))),capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert value.returncode==0,value.stderr
    plan=json.loads(value.stdout)
    assert not plan['registered'] and not plan['started'] and not plan['acceptance_passed']
    assert not output.exists() and not Path(str(output)+'.task.json').exists()


def test_owned_windows_handle_resource_metrics(tmp_path):
    import os
    import subprocess
    if os.name!='nt':pytest.skip('Windows process handle metrics')
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(2)'])
    try:
        value=module.child_resources(child)
        assert value['available'],value
        assert value['rss_bytes']>0 and value['cpu_seconds']>=0
        assert value['creation_filetime']>0 and value['priority_class']>0
    finally:
        child.terminate();child.wait(timeout=5)


def test_native_supervisor_short_process_has_job_receipt(tmp_path):
    import os
    import subprocess
    if os.name!='nt':pytest.skip('Windows Job Object')
    script=tmp_path/'small.py';script.write_text('print("done")')
    entry=Path(__file__).resolve().parents[2]/'scripts/supervise_endurance.py'
    output=tmp_path/'native'
    result=subprocess.run([sys.executable,str(entry),'--directory',str(output),'--script',str(script),'--seconds','5'],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    receipt=json.loads((tmp_path/'native.supervisor.json').read_text())
    assert receipt['kill_on_supervisor_exit'] and receipt['child_exit_confirmed']
    assert not receipt['acceptance_passed']
