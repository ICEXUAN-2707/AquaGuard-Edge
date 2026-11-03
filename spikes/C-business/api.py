"""prototype_only: authenticated local event API; no ingestion endpoint."""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import sqlite3
from uuid import uuid4

from fastapi import FastAPI, Depends, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from edge.contracts.api_models import AckRequest, AckResponse, EventDetailResponse, EventListResponse
from edge.contracts.api_models import LiveSnapshot, AssessmentResponse, SyncStatus, ExperimentResult
from projections import Projections, Unavailable
from edge.contracts.models import ApiError, _aware
from store import Store, Conflict, IdempotencyConflict, NotFound, VersionConflict, canonical


def create_app(store: Store, *, token: str, cursor_key: bytes, clock=None):
    if not isinstance(token,str) or len(token)<24 or not isinstance(cursor_key,bytes) or len(cursor_key)<32:
        raise ValueError("explicit token >=24 characters and cursor key >=32 bytes required")
    clock=clock or (lambda: datetime.now(timezone.utc).isoformat())
    projections=Projections(store.path)
    app=FastAPI(title="AquaGuard C prototype",docs_url=None,redoc_url=None,openapi_url=None)

    def error(status,code,details=None):
        body=ApiError.model_validate(dict(code=code,message=code,request_id=str(uuid4()),details=details or {}))
        return JSONResponse(status_code=status,content=body.model_dump(mode="json"))

    async def authorize(authorization: str | None=Header(default=None)):
        expected="Bearer "+token
        if authorization is None or not hmac.compare_digest(authorization.encode(),expected.encode()):
            from fastapi import HTTPException
            raise HTTPException(status_code=401)

    from starlette.exceptions import HTTPException

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        return error(exc.status_code,"UNAUTHORIZED" if exc.status_code==401 else "NOT_FOUND" if exc.status_code==404 else "BAD_REQUEST")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return error(400,"BAD_REQUEST")

    @app.exception_handler(NotFound)
    async def missing(request,exc):
        return error(404,"NOT_FOUND")

    @app.exception_handler(VersionConflict)
    async def version_conflict(request,exc):
        return error(409,"VERSION_CONFLICT",dict(expected_version=exc.expected,actual_version=exc.actual))

    @app.exception_handler(IdempotencyConflict)
    async def conflict(request,exc):
        return error(409,"IDEMPOTENCY_CONFLICT")

    @app.exception_handler(Conflict)
    async def business_error(request,exc):
        return error(400,"BAD_REQUEST")

    @app.exception_handler(sqlite3.Error)
    async def database_error(request,exc):
        return error(503,"SERVICE_UNAVAILABLE")

    @app.exception_handler(Unavailable)
    async def unavailable(request,exc):
        return error(503,"SERVICE_UNAVAILABLE")

    def pack(value):
        raw=canonical(value).encode()
        signature=hmac.new(cursor_key,raw,hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature+raw).decode()

    def unpack(value,scope):
        try:
            if len(value)>2048:
                raise ValueError()
            data=base64.b64decode(value,altchars=b"-_",validate=True)
            signature,raw=data[:32],data[32:]
            if not hmac.compare_digest(signature,hmac.new(cursor_key,raw,hashlib.sha256).digest()):
                raise ValueError()
            payload=json.loads(raw)
            if payload["scope"]!=scope or payload["v"]!=1:
                raise ValueError()
            return (_aware(payload["created_at"]),payload["event_id"])
        except (ValueError,KeyError,TypeError,UnicodeError):
            from fastapi import HTTPException
            raise HTTPException(status_code=400) from None

    @app.get("/api/events",response_model=EventListResponse,dependencies=[Depends(authorize)])
    def events(device_id: str | None=Query(default=None,min_length=1),
               lifecycle: str | None=None,cursor: str | None=None,limit: int=Query(default=20,ge=1,le=100)):
        if lifecycle not in (None,"OPEN","RESOLVED","CLOSED"):
            from fastapi import HTTPException
            raise HTTPException(status_code=400)
        scope=dict(device_id=device_id,lifecycle=lifecycle)
        after=None if cursor is None else unpack(cursor,scope)
        # Controlled prototype dataset: sort parsed instants, not ISO strings
        # whose timezone offsets can differ. SQL indexed projection is future work.
        with store.connection() as db:
            items=[json.loads(r[0]) for r in db.execute("SELECT body FROM events")]
        def key(event):
            return (_aware(event["created_at"]),event["event_id"])
        items=sorted((e for e in items if (device_id is None or e["device_id"]==device_id)
                      and (lifecycle is None or e["lifecycle"]==lifecycle)
                      and (after is None or key(e)<after)),key=key,reverse=True)
        page=items[:limit]
        next_cursor=None
        if len(items)>limit:
            next_cursor=pack(dict(v=1,scope=scope,created_at=page[-1]["created_at"],event_id=page[-1]["event_id"]))
        return dict(schema_version="1.1",items=page,next_cursor=next_cursor)

    @app.get("/api/events/{event_id}",response_model=EventDetailResponse,dependencies=[Depends(authorize)])
    def detail(event_id: str):
        return store.detail(event_id)

    @app.post("/api/events/{event_id}/ack",response_model=AckResponse,dependencies=[Depends(authorize)])
    def ack(event_id: str,body: AckRequest):
        return store.ack(event_id,body.model_dump(mode="json"),now=clock(),authorized=True)

    @app.get("/api/devices/{device_id}/live",response_model=LiveSnapshot,dependencies=[Depends(authorize)])
    def live(device_id: str):
        return projections.read("live",device_id,now=clock())

    @app.get("/api/devices/{device_id}/assessment",response_model=AssessmentResponse,dependencies=[Depends(authorize)])
    def assessment(device_id: str):
        return projections.read("assessment",device_id,now=clock())

    @app.get("/api/sync/status",response_model=SyncStatus,dependencies=[Depends(authorize)])
    def sync(device_id: str | None=Query(default=None,min_length=1)):
        return projections.sync(device_id)

    @app.get("/api/experiments/{trial_id}",response_model=ExperimentResult,dependencies=[Depends(authorize)])
    def experiment(trial_id: str):
        return projections.read("experiment",trial_id,now=clock())

    return app
