"""Local-only prototype launcher. No real cloud, notifications or hardware."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from api import create_app
from policy import Policy
from projections import Projections
from water import WaterService


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def seed(path,*,ttl_seconds,clear_seconds):
    """Fresh database only. Synthetic fixtures are never refreshed on serve."""
    policy=Policy(ttl_seconds,clear_seconds)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb"):
        pass
    service=WaterService(path)
    now=utcnow()
    observation=dict(schema_version="1.1",observation_id=str(uuid4()),device_id="demo01",
        sensor_type="water",boot_id="demo-boot",seq=0,uptime_ms=0,event_time=None,
        received_at=now,time_basis="RECEIVED_FALLBACK",value=dict(wet=True),quality="valid",source="simulation")
    result=service.ingest(observation,now=now,policy=policy,policy_version="demo-v1",
                          trusted_device="demo01",trusted_source="simulation",escalation_level="L2")
    queries=Projections(path)
    unknown=dict(state="unknown",age_sec=None,coverage_ratio=0)
    queries.publish("live",dict(schema_version="1.1",device_id="demo01",captured_at=now,
        sensor_summary=dict(flow=unknown,water=dict(state="wet",age_sec=0,coverage_ratio=0),presence=unknown),
        data_quality="DEGRADED",cloud_status="UNKNOWN",origin="simulation"),captured_at=now,ttl_seconds=ttl_seconds)
    queries.publish("assessment",dict(schema_version="1.1",assessment=dict(
        schema_version="1.1",assessment_id=str(uuid4()),window_id="demo-no-computed-window",device_id="demo01",
        situation="UNKNOWN",inference_mode="fallback",model_version="demo-placeholder-v1",model_score=None,
        data_quality="UNAVAILABLE",reason_codes=["DEMO_NO_B_INFERENCE"],origin="simulation"),
        safety_signals=[result["signal"]]),captured_at=now,ttl_seconds=ttl_seconds)
    queries.publish("experiment",dict(schema_version="1.1",trial_id="demo-trial",source="simulation",
        status="PLANNED",started_at=None,ended_at=None,asset_refs=[]),captured_at=now)
    return result["event"]["event_id"]


def tick(service,now):
    from context_events import ContextEvents
    ContextEvents(service.path).expire(now=now)
    with service.connection() as db:
        rows=db.execute("SELECT device_id,body FROM water_state").fetchall()
    failed=False
    for row in rows:
        try:
            state=json.loads(row[1])
            config=json.loads(state["config"])
            service.expire(row[0],now=now,policy=Policy(config["ttl"],config["clear"]),policy_version=config["version"])
        except Exception:
            failed=True  # One broken device must not starve remaining devices.
    if failed:
        raise ValueError("one or more water timers failed")


def build(path,*,token,cursor_key,interval=0.25,clock=utcnow,simulate=False,journal=None):
    if not isinstance(interval,(int,float)) or isinstance(interval,bool) or not 0.05<=interval<=60:
        raise ValueError("timer interval must be 0.05..60 seconds")
    if not Path(path).is_file():
        raise ValueError("database missing; seed a new demo or supply an existing C water database")
    service=WaterService(path)
    app=create_app(service,token=token,cursor_key=cursor_key,clock=clock)
    app.state.timer_error=False
    simulation=None
    if simulate and journal is not None:
        raise ValueError('choose generated simulation or MQTT journal')
    if journal is not None:
        from mqtt_journal import JournalRuntime
        simulation=JournalRuntime(path,Path(path).parent/(Path(path).name+'.checkpoints'),
                                  datetime.fromisoformat(clock().replace('Z','+00:00')),journal)
    if simulate:
        from online import Simulation
        simulation=Simulation(path,Path(path).parent/(Path(path).name+'.checkpoints'),
                              datetime.fromisoformat(clock().replace('Z','+00:00')))
    async def advance():
        try:
            now=clock()
            if simulation is not None:
                await asyncio.to_thread(simulation.step,datetime.fromisoformat(now.replace('Z','+00:00')))
            await asyncio.to_thread(tick,service,now)
            app.state.timer_error=False
        except Exception as exc:
            app.state.timer_error=True
            import traceback
            frame=traceback.extract_tb(exc.__traceback__)[-1]
            logging.getLogger("aquaguard.prototype").error("water timer failed (%s at %s:%s); inspect database/config/clock",type(exc).__name__,Path(frame.filename).name,frame.lineno)

    @asynccontextmanager
    async def lifespan(app):
        stop=asyncio.Event()
        await advance()  # Evaluate persisted evidence before accepting requests.
        async def loop():
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(),timeout=interval)
                except asyncio.TimeoutError:
                    await advance()
        task=asyncio.create_task(loop())
        try:
            yield
        finally:
            stop.set()
            await task
    app.router.lifespan_context=lifespan

    # Vite output is optional. API-only startup remains supported.
    built=ROOT/"web/dist"
    if (built/"c.html").is_file() and (built/"assets").is_dir():
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse
        app.mount("/assets",StaticFiles(directory=built/"assets"),name="business-assets")
        @app.get("/",include_in_schema=False)
        @app.get("/c.html",include_in_schema=False)
        def business_page():
            return FileResponse(built/"c.html")

    @app.get("/health",include_in_schema=False)
    def health():
        from fastapi.responses import JSONResponse
        failed=app.state.timer_error
        return JSONResponse(status_code=503 if failed else 200,
                            content=dict(status="degraded" if failed else "ok",prototype_only=True))
    return app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    demo=sub.add_parser("seed")
    demo.add_argument("--db",type=Path,required=True)
    demo.add_argument("--ttl",type=float,required=True)
    demo.add_argument("--clear",type=float,required=True)
    serve=sub.add_parser("serve")
    serve.add_argument("--db",type=Path,required=True)
    serve.add_argument("--port",type=int,default=8010)
    serve.add_argument("--simulate",action="store_true",help="continuous simulation; demo01 only; no cloud")
    worker=sub.add_parser("worker",help="bounded Mock-only worker; no network")
    worker.add_argument("--db",type=Path,required=True)
    worker.add_argument("--mode",choices=["accept","temporary","permanent","exception"],required=True)
    worker.add_argument("--steps",type=int,default=1)
    worker.add_argument("--interval",type=float,default=1)
    args=parser.parse_args()
    try:
        if args.command=="seed":
            event_id=seed(args.db,ttl_seconds=args.ttl,clear_seconds=args.clear)
            print(json.dumps(dict(prototype_only=True,device_id="demo01",event_id=event_id)))
            return 0
        if args.command=="worker":
            if not args.db.is_file() or not 1<=args.steps<=10000 or not 0.05<=args.interval<=60:
                raise ValueError("existing database, steps 1..10000 and interval 0.05..60 required")
            from outbox import Worker
            from delivery import DeliveryService
            from adapters.mock import MockAdapter
            delivery=DeliveryService(Worker(args.db),MockAdapter(args.mode))
            try:
                for index in range(args.steps):
                    print(json.dumps(dict(prototype_only=True,provider="mock",result=delivery.step(now=utcnow()))),flush=True)
                    if index+1<args.steps:
                        time.sleep(args.interval)
            finally:
                delivery.close()
            return 0
        if not 1<=args.port<=65535:
            raise ValueError("port must be 1..65535")
        token=os.environ.get("AQUAGUARD_C_TOKEN","")
        try:
            key=bytes.fromhex(os.environ.get("AQUAGUARD_C_CURSOR_KEY",""))
        except ValueError:
            raise ValueError("AQUAGUARD_C_CURSOR_KEY must be hex") from None
        # Validate secrets before opening or changing any database.
        if len(token)<24 or len(key)<32:
            raise ValueError("set AQUAGUARD_C_TOKEN >=24 chars and AQUAGUARD_C_CURSOR_KEY >=64 hex chars")
        if args.simulate and not args.db.exists():
            args.db.parent.mkdir(parents=True,exist_ok=True)
            WaterService(args.db)
        app=build(args.db,token=token,cursor_key=key,simulate=args.simulate)
        import uvicorn
        uvicorn.run(app,host="127.0.0.1",port=args.port,access_log=False)
        return 0
    except KeyboardInterrupt:
        return 0
    except (ValueError,OSError) as exc:
        print(f"C prototype startup failed: {exc}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
