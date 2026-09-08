from __future__ import annotations

import hmac
import json
import logging
import shutil
import time
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from xray import __version__
from xray.api.schemas import (
    HealthResponse,
    SessionStartRequest,
    SessionStartResponse,
    XRayRequest,
    XRayResponse,
)
from xray.config import Settings, load_settings
from xray.db import Database
from xray.media import FrameExtractor, PathResolutionError, SecurePathResolver
from xray.metadata import CompositeMetadataProvider
from xray.recognition import OpenCvSFaceBackend
from xray.recognition.analyzer import SceneAnalyzer


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("xray.api")


class Services:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings.database.path)
        self.database.initialize()
        self.resolver = SecurePathResolver(settings)
        self.extractor = FrameExtractor(settings)
        self.recognizer = OpenCvSFaceBackend(settings)
        self.metadata = CompositeMetadataProvider(settings)
        self.analyzer = SceneAnalyzer(
            settings, self.database, self.resolver, self.extractor, self.recognizer, self.metadata
        )
        self.metrics = {"requests": 0, "cache_hits": 0, "cache_misses": 0, "errors": 0}


@lru_cache(maxsize=1)
def services() -> Services:
    return Services(load_settings())


def require_auth(authorization: str | None = Header(default=None)) -> None:
    expected = services().settings.api_token.get_secret_value()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer token required")
    supplied = authorization[7:]
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")


app = FastAPI(title="Kodi X-Ray", version=__version__, docs_url=None, redoc_url=None)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    started = time.monotonic()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = round((time.monotonic() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "timestamp": time.time(),
                    "level": "info",
                    "request_id": request_id,
                    "operation": f"{request.method} {request.url.path}",
                    "status": response.status_code if response else 500,
                    "latency_ms": elapsed,
                },
                separators=(",", ":"),
            )
        )
        if response:
            response.headers["X-Request-ID"] = request_id


def _checks() -> dict[str, object]:
    svc = services()
    media_checks = []
    for root in svc.settings.media.roots:
        media_checks.append({"path": str(root), "readable": root.is_dir() and bool(root.stat())})
    return {
        "api": True,
        "db": svc.database.health(),
        "model": {
            "ready": svc.recognizer.ready,
            "id": svc.recognizer.model_id,
            "version": svc.recognizer.model_version,
            "error": getattr(svc.recognizer, "load_error", None),
        },
        "media": media_checks,
        "ffmpeg": Path(svc.settings.media.ffmpeg).is_file(),
        "ffprobe": Path(svc.settings.media.ffprobe).is_file(),
    }


@app.get("/health", response_model=HealthResponse)
@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok", "version": __version__, "checks": _checks()}


@app.get("/ready", response_model=HealthResponse)
@app.get("/api/v1/ready", response_model=HealthResponse)
def ready():
    checks = _checks()
    okay = bool(checks["db"] and checks["ffmpeg"] and checks["ffprobe"])
    okay = okay and bool(checks["model"]["ready"])
    okay = okay and all(item["readable"] for item in checks["media"])
    payload = {"status": "ready" if okay else "not-ready", "version": __version__, "checks": checks}
    return JSONResponse(status_code=200 if okay else 503, content=payload)


@app.post(
    "/api/v1/session/start",
    response_model=SessionStartResponse,
    dependencies=[Depends(require_auth)],
    status_code=202,
)
def session_start(request: SessionStartRequest) -> dict:
    svc = services()
    resolved = svc.resolver.resolve(request.media.file)
    probe = svc.extractor.probe(resolved.path)
    media_key = resolved.media_key(probe.duration)
    media_id = svc.database.upsert_media(
        media_key, resolved.path, probe.duration, svc.metadata.resolve_media(request.media)
    )
    cast = svc.metadata.get_cast(request.media)
    for person in cast:
        person_id = svc.database.upsert_person(person.external_id, person.name)
        svc.database.set_roles(media_id, person_id, person.roles)
        urls = list(person.image_urls)
        if person.external_id.startswith("tmdb:"):
            try:
                urls.extend(svc.metadata.get_person_images(person.external_id))
            except Exception:
                pass
        svc.database.enqueue_gallery(media_id, person_id, list(dict.fromkeys(urls)))
    gallery_ready, gallery_queued = svc.database.gallery_counts(
        media_id, svc.recognizer.model_id, svc.recognizer.model_version
    )
    return {
        "state": "accepted",
        "media_key": media_key,
        "gallery_ready": gallery_ready,
        "gallery_queued": gallery_queued,
    }


@app.post("/api/v1/xray", response_model=XRayResponse, dependencies=[Depends(require_auth)])
async def xray(request: XRayRequest) -> dict:
    svc = services()
    svc.metrics["requests"] += 1
    try:
        result = await run_in_threadpool(svc.analyzer.analyze, request)
    except (PathResolutionError, ValueError) as exc:
        svc.metrics["errors"] += 1
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        svc.metrics["errors"] += 1
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result["cache_hit"]:
        svc.metrics["cache_hits"] += 1
    else:
        svc.metrics["cache_misses"] += 1
    return result


@app.get("/api/v1/people/{person_id:path}/portrait", dependencies=[Depends(require_auth)])
def portrait(person_id: str):
    path = services().database.portrait(person_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="portrait unavailable")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/v1/metrics", dependencies=[Depends(require_auth)])
def metrics() -> dict:
    svc = services()
    return {**svc.metrics, **svc.database.stats(), "model_status": svc.recognizer.ready}


@app.exception_handler(PathResolutionError)
def path_error(_request: Request, exc: PathResolutionError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})
