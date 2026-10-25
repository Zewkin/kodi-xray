import json
from types import SimpleNamespace

from xray.config import Settings
from xray.media import FrameExtractor


def settings(tmp_path):
    return Settings.model_validate(
        {
            "media": {"roots": [str(tmp_path)]},
            "path_maps": [
                {"kodi_prefix": "nfs://nas/media/", "backend_prefix": str(tmp_path)}
            ],
            "api_token": "x" * 24,
        }
    )


def test_probe_is_cached_until_media_changes(monkeypatch, tmp_path):
    media = tmp_path / "video.mkv"
    media.write_bytes(b"first")
    calls = []
    payload = {
        "streams": [
            {
                "width": 1920,
                "height": 1080,
                "codec_name": "hevc",
                "color_transfer": "smpte2084",
            }
        ],
        "format": {"duration": "100.5"},
    }

    def run(*_args, **_kwargs):
        calls.append(1)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("xray.media.frames.subprocess.run", run)
    extractor = FrameExtractor(settings(tmp_path))

    assert extractor.probe(media) == extractor.probe(media)
    assert len(calls) == 1

    media.write_bytes(b"changed-size")
    extractor.probe(media)
    assert len(calls) == 2
