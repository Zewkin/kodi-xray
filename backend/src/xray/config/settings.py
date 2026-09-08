from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator


class ServerSettings(BaseModel):
    listen: str = "0.0.0.0"
    port: int = Field(8787, ge=1, le=65535)
    workers: int = Field(1, ge=1, le=4)


class PathMap(BaseModel):
    kodi_prefix: str
    backend_prefix: Path

    @field_validator("kodi_prefix")
    @classmethod
    def nfs_prefix_only(cls, value: str) -> str:
        if not value.lower().startswith("nfs://") or not value.endswith("/"):
            raise ValueError("kodi_prefix must be an nfs:// prefix ending in /")
        return value


class MediaSettings(BaseModel):
    roots: list[Path] = Field(default_factory=lambda: [Path("/media")])
    ffmpeg: str = "/usr/bin/ffmpeg"
    ffprobe: str = "/usr/bin/ffprobe"
    frame_dir: Path = Path("/run/xray")
    max_decode_width: int = Field(1280, ge=320, le=3840)


class DatabaseSettings(BaseModel):
    path: Path = Path("/var/lib/xray/xray.db")


class RecognitionSettings(BaseModel):
    provider: Literal["opencv_sface"] = "opencv_sface"
    model_dir: Path = Path("/var/lib/xray/models")
    detector_model: str = "face_detection_yunet_2023mar.onnx"
    recognizer_model: str = "face_recognition_sface_2021dec.onnx"
    model_id: str = "opencv-sface"
    model_version: str = "2021dec"
    detector_threshold: float = Field(0.45, ge=0, le=1)
    match_threshold: float = Field(0.48, ge=-1, le=1)
    match_margin: float = Field(0.10, ge=0, le=2)
    min_face_pixels: int = Field(42, ge=16, le=512)


class AnalysisSettings(BaseModel):
    neighbor_offset_sec: float = Field(0.5, ge=0, le=2)
    max_faces: int = Field(12, ge=1, le=32)
    cache_window_sec: float = Field(0.5, gt=0, le=3)


class CacheSettings(BaseModel):
    max_bytes: int = Field(24 * 1024**3, ge=1024**3)


class MetadataSettings(BaseModel):
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p/w500"
    tvmaze_enabled: bool = False
    tvmaze_base_url: str = "https://api.tvmaze.com"
    max_cast: int = Field(80, ge=1, le=100)
    reference_images_per_actor: int = Field(5, ge=1, le=8)


class DebugSettings(BaseModel):
    store_frames: bool = False


class BackgroundIndexSettings(BaseModel):
    enabled: bool = False


class Settings(BaseModel):
    server: ServerSettings = Field(default_factory=ServerSettings)
    media: MediaSettings = Field(default_factory=MediaSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    recognition: RecognitionSettings = Field(default_factory=RecognitionSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    debug: DebugSettings = Field(default_factory=DebugSettings)
    background_index: BackgroundIndexSettings = Field(default_factory=BackgroundIndexSettings)
    path_maps: list[PathMap]
    api_token: SecretStr
    tmdb_token: SecretStr | None = None

    @field_validator("path_maps")
    @classmethod
    def require_maps(cls, value: list[PathMap]) -> list[PathMap]:
        if not value:
            raise ValueError("at least one path map is required")
        return value


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    config_path = Path(os.environ.get("XRAY_CONFIG", "/etc/xray/xray.yaml"))
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    token = os.environ.get("XRAY_API_TOKEN", "")
    if len(token) < 24:
        raise RuntimeError("XRAY_API_TOKEN must contain at least 24 characters")
    raw["api_token"] = token
    tmdb_token = os.environ.get("XRAY_TMDB_TOKEN")
    if tmdb_token:
        raw["tmdb_token"] = tmdb_token
    return Settings.model_validate(raw)
