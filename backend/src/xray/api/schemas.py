from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class CastMember(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    roles: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)


class MediaPayload(BaseModel):
    file: str
    media_type: Literal["movie", "episode", "video", "unknown"] = "unknown"
    title: str | None = None
    year: int | None = None
    show: str | None = None
    season: int | None = None
    episode: int | None = None
    unique_ids: dict[str, str] = Field(default_factory=dict)
    cast: list[CastMember] = Field(default_factory=list)


class SessionStartRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    kodi_version: str | None = None
    platform: str | None = None
    media: MediaPayload


class SessionStartResponse(BaseModel):
    state: Literal["accepted"] = "accepted"
    media_key: str
    gallery_ready: int = 0
    gallery_queued: int = 0


class PlaybackPayload(BaseModel):
    position: float = Field(ge=0)


class XRayRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    media: MediaPayload
    playback: PlaybackPayload


class ActorResponse(BaseModel):
    id: str
    name: str


class BBoxResponse(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class PersonResponse(BaseModel):
    actor: ActorResponse
    roles: list[str]
    bbox: BBoxResponse
    similarity: float
    top2_margin: float
    accepted: bool


class FrameResponse(BaseModel):
    width: int
    height: int


class XRayResponse(BaseModel):
    timestamp: float
    media_key: str
    frame: FrameResponse
    people: list[PersonResponse]
    unknown_faces: int
    cache_hit: bool = False
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, Any]

