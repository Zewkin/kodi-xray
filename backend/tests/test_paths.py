from pathlib import Path

import pytest

from xray.config.settings import PathMap, Settings
from xray.media.paths import PathResolutionError, SecurePathResolver


def settings(root: Path) -> Settings:
    return Settings.model_validate(
        {
            "api_token": "x" * 32,
            "media": {"roots": [str(root)]},
            "database": {"path": str(root / "test.db")},
            "path_maps": [{"kodi_prefix": "nfs://nas/media/", "backend_prefix": str(root)}],
        }
    )


def test_maps_url_decoded_file_inside_root(tmp_path):
    movie = tmp_path / "Some Film.mkv"
    movie.write_bytes(b"video")
    resolved = SecurePathResolver(settings(tmp_path)).resolve("nfs://NAS/media/Some%20Film.mkv")
    assert resolved.path == movie


@pytest.mark.parametrize(
    "value",
    [
        "nfs://nas/media/../etc/passwd",
        "nfs://nas/media/%2e%2e/etc/passwd",
        "file:///etc/passwd",
        "nfs://user:password@nas/media/movie.mkv",
        "nfs://nas/media/movie.mkv?anything=1",
    ],
)
def test_rejects_unsafe_paths(tmp_path, value):
    (tmp_path / "movie.mkv").write_bytes(b"video")
    with pytest.raises(PathResolutionError):
        SecurePathResolver(settings(tmp_path)).resolve(value)


def test_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside-xray-test.mkv"
    outside.write_bytes(b"video")
    try:
        (tmp_path / "escape.mkv").symlink_to(outside)
        with pytest.raises(PathResolutionError):
            SecurePathResolver(settings(tmp_path)).resolve("nfs://nas/media/escape.mkv")
    finally:
        outside.unlink(missing_ok=True)

