from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import httpx

from xray import __version__
from xray.config import load_settings
from xray.db import Database
from xray.media import FrameExtractor, SecurePathResolver
from xray.recognition import OpenCvSFaceBackend


def _doctor() -> int:
    settings = load_settings()
    database = Database(settings.database.path)
    database.initialize()
    recognizer = OpenCvSFaceBackend(settings)
    checks = {
        "media_roots": all(root.is_dir() and os.access(root, os.R_OK) for root in settings.media.roots),
        "media_roots_not_writable": all(not os.access(root, os.W_OK) for root in settings.media.roots),
        "ffmpeg": shutil.which(settings.media.ffmpeg) is not None,
        "ffprobe": shutil.which(settings.media.ffprobe) is not None,
        "database": database.health(),
        "model": recognizer.ready,
        "disk_free_bytes": shutil.disk_usage(settings.database.path.parent).free,
        "background_index_disabled": not settings.background_index.enabled,
    }
    print(json.dumps(checks, indent=2))
    return 0 if all(value for key, value in checks.items() if key != "disk_free_bytes") else 1


def _health() -> int:
    settings = load_settings()
    url = f"http://127.0.0.1:{settings.server.port}/ready"
    response = httpx.get(url, timeout=3)
    print(json.dumps(response.json(), indent=2))
    return 0 if response.status_code == 200 else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="xrayctl")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("doctor")
    sub.add_parser("health")
    cache = sub.add_parser("cache")
    cache_sub = cache.add_subparsers(dest="cache_command", required=True)
    cache_sub.add_parser("stats")
    prune = cache_sub.add_parser("prune")
    prune.add_argument("--days", type=int, default=30)
    media = sub.add_parser("media")
    media_sub = media.add_subparsers(dest="media_command", required=True)
    media_sub.add_parser("list")
    invalidate = media_sub.add_parser("invalidate")
    invalidate.add_argument("media_key")
    gallery = sub.add_parser("gallery")
    gallery_sub = gallery.add_subparsers(dest="gallery_command", required=True)
    gallery_sub.add_parser("status")
    rebuild = gallery_sub.add_parser("rebuild")
    rebuild.add_argument("--person", help="external person ID, for example tmdb:3223")
    sub.add_parser("benchmark")
    args = parser.parse_args()
    settings = load_settings()
    database = Database(settings.database.path)
    database.initialize()
    if args.command == "doctor":
        raise SystemExit(_doctor())
    if args.command == "health":
        raise SystemExit(_health())
    if args.command == "status":
        payload = {"version": __version__, "database": database.stats()}
        print(json.dumps(payload, indent=2))
        return
    if args.command == "cache" and args.cache_command == "stats":
        print(json.dumps(database.stats(), indent=2))
        return
    if args.command == "cache" and args.cache_command == "prune":
        deleted = database.prune_analyses(time.time() - args.days * 86400)
        print(json.dumps({"deleted": deleted}))
        return
    if args.command == "media" and args.media_command == "list":
        with database.connect() as connection:
            rows = [dict(row) for row in connection.execute("SELECT media_key,path,duration,updated_at FROM media")]
        print(json.dumps(rows, indent=2))
        return
    if args.command == "media" and args.media_command == "invalidate":
        print(json.dumps({"deleted": database.invalidate_media(args.media_key)}))
        return
    if args.command == "gallery" and args.gallery_command == "status":
        print(json.dumps(database.gallery_status(), indent=2))
        return
    if args.command == "gallery" and args.gallery_command == "rebuild":
        print(json.dumps(database.rebuild_gallery(args.person), indent=2))
        return
    if args.command == "benchmark":
        started = time.monotonic()
        completed = subprocess.run([settings.media.ffmpeg, "-version"], capture_output=True, timeout=5).returncode == 0
        print(json.dumps({"ffmpeg_start_ms": round((time.monotonic() - started) * 1000, 2), "ok": completed}))


if __name__ == "__main__":
    main()
