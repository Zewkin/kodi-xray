from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from xray.config import Settings


class MediaToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProbeResult:
    duration: float
    width: int
    height: int
    codec: str
    color_transfer: str | None
    sample_aspect_ratio: str | None
    display_aspect_ratio: str | None
    rotation: int

    @property
    def is_hdr(self) -> bool:
        return (self.color_transfer or "").lower() in {"smpte2084", "arib-std-b67"}


class FrameExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings

    def probe(self, media: Path) -> ProbeResult:
        command = [
            self.settings.media.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,color_transfer,sample_aspect_ratio,display_aspect_ratio:stream_tags=rotate:format=duration",
            "-of",
            "json",
            str(media),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        if result.returncode:
            raise MediaToolError(f"ffprobe failed: {result.stderr[-500:]}")
        try:
            payload = json.loads(result.stdout)
            stream = payload["streams"][0]
            duration = float(payload["format"]["duration"])
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MediaToolError("ffprobe returned incomplete video metadata") from exc
        rotation = int((stream.get("tags") or {}).get("rotate", 0))
        width, height = int(stream["width"]), int(stream["height"])
        if abs(rotation) % 180 == 90:
            width, height = height, width
        return ProbeResult(
            duration=duration,
            width=width,
            height=height,
            codec=str(stream.get("codec_name") or "unknown"),
            color_transfer=stream.get("color_transfer"),
            sample_aspect_ratio=stream.get("sample_aspect_ratio"),
            display_aspect_ratio=stream.get("display_aspect_ratio"),
            rotation=rotation,
        )

    def extract(self, media: Path, timestamp: float, probe: ProbeResult) -> tuple[Path, list[Path]]:
        base = self.settings.media.frame_dir
        base.mkdir(parents=True, exist_ok=True, mode=0o750)
        workspace = Path(tempfile.mkdtemp(prefix="analysis-", dir=base))
        offsets = (-self.settings.analysis.neighbor_offset_sec, 0.0, self.settings.analysis.neighbor_offset_sec)
        frames: list[Path] = []
        try:
            for index, offset in enumerate(offsets):
                position = max(0.0, min(probe.duration, timestamp + offset))
                target = workspace / f"frame-{index}.jpg"
                self._extract_one(media, position, target, probe)
                frames.append(target)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        return workspace, frames

    def cleanup(self, workspace: Path) -> None:
        if not self.settings.debug.store_frames:
            shutil.rmtree(workspace, ignore_errors=True)

    def _extract_one(self, media: Path, position: float, target: Path, probe: ProbeResult) -> None:
        width = self.settings.media.max_decode_width
        scale = f"scale='min({width},iw)':-2"
        filters = scale
        if probe.is_hdr:
            filters = (
                scale + ",zscale=t=linear:npl=100,format=gbrpf32le,"
                "tonemap=tonemap=hable:desat=0,"
                "zscale=p=bt709:t=bt709:m=bt709:r=tv,format=yuv420p"
            )
        command = [
            self.settings.media.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{position:.3f}",
            "-i",
            str(media),
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            "-vf",
            filters,
            "-q:v",
            "2",
            "-y",
            str(target),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
        if result.returncode and probe.is_hdr:
            command[command.index("-vf") + 1] = scale
            result = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
        if result.returncode or not target.is_file():
            raise MediaToolError(f"ffmpeg frame extraction failed: {result.stderr[-500:]}")
