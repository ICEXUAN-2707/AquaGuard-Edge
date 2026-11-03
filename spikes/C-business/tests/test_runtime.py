import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import json
import re
import urllib.request
import urllib.error

import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"spikes/C-business"))
import run as runtime
from test_api import TOKEN, http
from store import Store


def test_seed_is_explicit_and_never_overwrites(tmp_path):
    path=tmp_path/"demo.sqlite"
    event=runtime.seed(path,ttl_seconds=10,clear_seconds=2)
    original=Store(path).detail(event)
    with pytest.raises(FileExistsError):
        runtime.seed(path,ttl_seconds=10,clear_seconds=2)
    assert Store(path).detail(event)==original


def test_lifespan_expires_on_startup_and_stops(tmp_path):
    path=tmp_path/"demo.sqlite"
    event=runtime.seed(path,ttl_seconds=1,clear_seconds=2)
    from datetime import datetime,timedelta,timezone
    future=(datetime.now(timezone.utc)+timedelta(seconds=2)).isoformat()
    app=runtime.build(path,token=TOKEN,cursor_key=b"x"*32,clock=lambda:future)
    async def exercise():
        async with app.router.lifespan_context(app):
            assert Store(path).detail(event)["event"]["physical_status"]=="UNKNOWN"
            assert not app.state.timer_error
    asyncio.run(exercise())


def test_real_loopback_ack_timer_and_restart(tmp_path):
    path=tmp_path/"demo.sqlite"
    event=runtime.seed(path,ttl_seconds=1,clear_seconds=2)
    env=os.environ.copy()
    env.update(AQUAGUARD_C_TOKEN=TOKEN,AQUAGUARD_C_CURSOR_KEY="78"*32)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    cmd=[sys.executable,str(ROOT/"spikes/C-business/run.py"),"serve","--db",str(path),"--port",str(port)]
    def request(route,body=None):
        req=urllib.request.Request(f"http://127.0.0.1:{port}"+route,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=2) as response:
            return json.load(response)
    def start():
        process=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    raise AssertionError(process.communicate())
                try:
                    request("/health")
                    return process
                except (urllib.error.URLError,TimeoutError):
                    time.sleep(0.05)
            raise AssertionError("startup timeout")
        except BaseException:
            process.terminate()
            process.communicate(timeout=10)
            raise
    process=start()
    try:
        if (ROOT/"web/dist/c.html").is_file():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/c.html",timeout=2) as response:
                html=response.read().decode("utf-8")
            assert 'lang="zh-CN"' in html
            scripts=re.findall(r'src="(/assets/[^\"]+[.]js)"',html)
            assert scripts
            with urllib.request.urlopen(f"http://127.0.0.1:{port}"+scripts[0],timeout=2) as response:
                assert response.status==200 and len(response.read())>100
        detail=request("/api/events/"+event)
        ack=dict(schema_version="1.1",expected_version=detail["event"]["version"],idempotency_key="runtime-ack",ack_type="ACKNOWLEDGE")
        # Wait for expiry first, so timer cannot race expected_version in this check.
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            detail=request("/api/events/"+event)
            if detail["event"]["physical_status"]=="UNKNOWN":
                break
            time.sleep(0.05)
        assert detail["event"]["physical_status"]=="UNKNOWN"
        ack["expected_version"]=detail["event"]["version"]
        original=request("/api/events/"+event+"/ack",ack)
        assert original["event"]["physical_status"]=="UNKNOWN"
        with pytest.raises(urllib.error.HTTPError) as exc:
            request("/api/devices/demo01/live")
        assert exc.value.code==503
    finally:
        process.terminate()
        process.communicate(timeout=10)
    process=start()
    try:
        assert request("/api/events/"+event+"/ack",ack)==original
        assert request("/api/sync/status")["pending_count"]==3
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_missing_credentials_fail_before_creating_database(tmp_path):
    path=tmp_path/"missing.sqlite"
    env=os.environ.copy()
    env.pop("AQUAGUARD_C_TOKEN",None)
    env.pop("AQUAGUARD_C_CURSOR_KEY",None)
    result=subprocess.run([sys.executable,str(ROOT/"spikes/C-business/run.py"),"serve","--db",str(path)],
                          env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode==2
    assert "AQUAGUARD_C_TOKEN" in result.stderr
    assert not path.exists()


def test_timer_failure_is_visible_and_shutdown_finishes(tmp_path,monkeypatch):
    path=tmp_path/"demo.sqlite"
    runtime.seed(path,ttl_seconds=10,clear_seconds=2)
    def fail(*args):
        raise ValueError("injected internal details")
    monkeypatch.setattr(runtime,"tick",fail)
    app=runtime.build(path,token=TOKEN,cursor_key=b"x"*32)
    async def exercise():
        async with app.router.lifespan_context(app):
            assert app.state.timer_error
    asyncio.run(exercise())
    status,body=http(app,"GET","/health")
    assert status==503 and body==dict(status="degraded",prototype_only=True)
