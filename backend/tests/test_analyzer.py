from pathlib import Path
from types import SimpleNamespace

import numpy as np

from xray.api.schemas import XRayRequest
from xray.config import Settings
from xray.recognition.analyzer import SceneAnalyzer
from xray.recognition.backend import FaceObservation


class FakeResolved:
    def __init__(self, path: Path):
        self.path = path

    def media_key(self, _duration: float) -> str:
        return "media-key"


class FakeResolver:
    def __init__(self, path: Path):
        self.resolved = FakeResolved(path)

    def resolve(self, _file: str) -> FakeResolved:
        return self.resolved


class FakeExtractor:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.neighbor_calls = 0
        self.cleanup_calls = 0

    def probe(self, _path: Path):
        return SimpleNamespace(duration=100.0)

    def extract_central(self, _path: Path, _timestamp: float, _probe):
        return self.workspace, self.workspace / "central.jpg"

    def extract_neighbors(self, _path: Path, _timestamp: float, _probe, _workspace: Path):
        self.neighbor_calls += 1
        return [self.workspace / "left.jpg", self.workspace / "right.jpg"]

    def cleanup(self, _workspace: Path):
        self.cleanup_calls += 1


class FakeDatabase:
    def __init__(self):
        self.saved = None

    def upsert_media(self, *_args):
        return 1

    def media_has_roles(self, _media_id: int) -> bool:
        return True

    def get_cached(self, *_args):
        return None

    def gallery_for_media(self, *_args):
        return [
            {
                "person_id": 1,
                "external_id": "tmdb:1",
                "name": "Actor One",
                "roles": ["Hero"],
                "vector": np.asarray([1.0, 0.0], dtype=np.float32),
            },
            {
                "person_id": 2,
                "external_id": "tmdb:2",
                "name": "Actor Two",
                "roles": ["Rival"],
                "vector": np.asarray([0.0, 1.0], dtype=np.float32),
            },
        ]

    def put_analysis(self, *_args):
        self.saved = _args[-2]


class FakeRecognizer:
    model_id = "test-model"
    model_version = "1"
    ready = True

    def __init__(self, has_faces: bool = True):
        self.has_faces = has_faces

    def detect(self, _image: np.ndarray):
        if not self.has_faces:
            return []
        return [
            FaceObservation(
                bbox=(10.0, 20.0, 30.0, 40.0),
                landmarks=(),
                detector_confidence=0.9,
                raw=np.zeros(15, dtype=np.float32),
            )
        ]

    def align(self, image: np.ndarray, _face: FaceObservation) -> np.ndarray:
        return image

    def embed(self, image: np.ndarray) -> np.ndarray:
        vector = image[0, 0, :2].astype(np.float32)
        return vector / np.linalg.norm(vector)


class FakeMetadata:
    def get_cast(self, _media):
        return []


def settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "media": {"roots": [str(tmp_path)]},
            "path_maps": [
                {"kodi_prefix": "nfs://nas/media/", "backend_prefix": str(tmp_path)}
            ],
            "api_token": "x" * 24,
        }
    )


def request() -> XRayRequest:
    return XRayRequest.model_validate(
        {
            "client_id": "test-client",
            "media": {"file": "nfs://nas/media/video.mkv"},
            "playback": {"position": 10.0},
        }
    )


def analyzer(tmp_path: Path, recognizer: FakeRecognizer):
    extractor = FakeExtractor(tmp_path)
    instance = SceneAnalyzer(
        settings(tmp_path),
        FakeDatabase(),
        FakeResolver(tmp_path / "video.mkv"),
        extractor,
        recognizer,
        FakeMetadata(),
    )
    return instance, extractor


def frame(vector: tuple[float, float]) -> np.ndarray:
    image = np.zeros((100, 200, 3), dtype=np.float32)
    image[0, 0, :2] = vector
    return image


def test_no_faces_skips_neighbor_frames(monkeypatch, tmp_path):
    instance, extractor = analyzer(tmp_path, FakeRecognizer(has_faces=False))
    monkeypatch.setattr("xray.recognition.analyzer.load_bgr", lambda _path: frame((1.0, 0.0)))

    result = instance.analyze(request())

    assert result["people"] == []
    assert result["unknown_faces"] == 0
    assert extractor.neighbor_calls == 0
    assert extractor.cleanup_calls == 1


def test_confident_central_match_skips_neighbor_frames(monkeypatch, tmp_path):
    instance, extractor = analyzer(tmp_path, FakeRecognizer())
    monkeypatch.setattr("xray.recognition.analyzer.load_bgr", lambda _path: frame((1.0, 0.0)))

    result = instance.analyze(request())

    assert [person["actor"]["name"] for person in result["people"]] == ["Actor One"]
    assert extractor.neighbor_calls == 0


def test_ambiguous_central_match_falls_back_to_neighbors(monkeypatch, tmp_path):
    instance, extractor = analyzer(tmp_path, FakeRecognizer())
    monkeypatch.setattr("xray.recognition.analyzer.load_bgr", lambda _path: frame((1.0, 1.0)))

    result = instance.analyze(request())

    assert result["people"] == []
    assert result["unknown_faces"] == 1
    assert extractor.neighbor_calls == 1
