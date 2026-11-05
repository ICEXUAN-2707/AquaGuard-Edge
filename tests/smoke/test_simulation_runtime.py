"""Actual public entrypoint process, continuous scheduler and HTTP integration."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error


def test_public_simulation_runtime(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    env=os.environ.copy()
    env.update(AQUAGUARD_RUNTIME='simulation',AQUAGUARD_DEVICE_ID='demo01',
        AQUAGUARD_PORT=str(port),AQUAGUARD_DB=str(tmp_path/'online.sqlite'),
        AQUAGUARD_C_TOKEN='simulation-process-test-token',AQUAGUARD_C_CURSOR_KEY='78'*32)
    process=subprocess.Popen([sys.executable,'-m','edge'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    def request(path):
        req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,
            headers={'Authorization':'Bearer '+env['AQUAGUARD_C_TOKEN']})
        with urllib.request.urlopen(req,timeout=5) as response:
            return json.load(response)
    try:
        deadline=time.monotonic()+50
        first=None
        while time.monotonic()<deadline:
            assert process.poll() is None, process.communicate()[1]
            try:
                health=request('/health')
                assert health['status']=='ok'
                value=request('/api/devices/demo01/live')
                if first is None:
                    first=value['captured_at']
                elif value['captured_at']!=first:
                    break
            except urllib.error.HTTPError as exc:
                # Before first window there is no projection; later expiry is 503.
                assert exc.code in (404,503)
            except urllib.error.URLError:
                pass
            time.sleep(0.5)
        else:
            raise AssertionError('continuous input did not publish two windows')
        assert value['origin']=='simulation'
        assessment=request('/api/devices/demo01/assessment')
        assert assessment['assessment']['situation']=='ATTENDED_FLOW'
        assert assessment['safety_signals'][0]['value'] is False
        trial=request('/api/experiments/demo-trial')
        assert trial['status']=='RUNNING' and trial['asset_refs']
        assert request('/api/sync/status')['last_ack_level']=='NONE'
        assert request('/api/events')['items']==[]
        if os.path.isfile('web/dist/c.html'):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=5) as page:
                assert page.status==200 and 'assets/' in page.read().decode()
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_simulation_validates_before_database_creation(tmp_path):
    from edge.config import Settings,ConfigurationError
    from edge.app import create_app
    import pytest
    from unittest.mock import patch
    path=tmp_path/'must-not-exist.sqlite'
    with patch.dict(os.environ,dict(AQUAGUARD_RUNTIME='simulation',AQUAGUARD_DB=str(path),
                                   AQUAGUARD_C_TOKEN='',AQUAGUARD_C_CURSOR_KEY='')):
        with pytest.raises(ConfigurationError):
            create_app(Settings('demo01','127.0.0.1',8000))
    assert not path.exists()
