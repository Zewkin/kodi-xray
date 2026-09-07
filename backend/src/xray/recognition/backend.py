from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from xray.config import Settings


@dataclass(frozen=True)
class FaceObservation:
    bbox: tuple[float, float, float, float]
    landmarks: tuple[tuple[float, float], ...]
    detector_confidence: float
    raw: np.ndarray


class FaceRecognitionBackend(ABC):
    model_id: str
    model_version: str

    @property
    @abstractmethod
    def ready(self) -> bool: ...

    @abstractmethod
    def detect(self, image: np.ndarray) -> list[FaceObservation]: ...

    @abstractmethod
    def align(self, image: np.ndarray, face: FaceObservation) -> np.ndarray: ...

    @abstractmethod
    def embed(self, aligned_face: np.ndarray) -> np.ndarray: ...


class OpenCvSFaceBackend(FaceRecognitionBackend):
    """YuNet detection + SFace aligned embeddings via OpenCV DNN."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_id = settings.recognition.model_id
        self.model_version = settings.recognition.model_version
        self._detector = None
        self._recognizer = None
        self._load_error: str | None = None
        self._load()

    def _load(self) -> None:
        detector_path = self.settings.recognition.model_dir / self.settings.recognition.detector_model
        recognizer_path = self.settings.recognition.model_dir / self.settings.recognition.recognizer_model
        if not detector_path.is_file() or not recognizer_path.is_file():
            self._load_error = "model files are missing"
            return
        try:
            import cv2

            self._detector = cv2.FaceDetectorYN.create(
                str(detector_path),
                "",
                (320, 320),
                self.settings.recognition.detector_threshold,
                0.3,
                5000,
            )
            self._recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
        except Exception as exc:  # OpenCV reports several non-standard exception types.
            self._load_error = str(exc)
            self._detector = None
            self._recognizer = None

    @property
    def ready(self) -> bool:
        return self._detector is not None and self._recognizer is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def detect(self, image: np.ndarray) -> list[FaceObservation]:
        if not self.ready:
            raise RuntimeError(self._load_error or "recognition model unavailable")
        height, width = image.shape[:2]
        self._detector.setInputSize((width, height))
        _, matrix = self._detector.detect(image)
        if matrix is None:
            return []
        observations = []
        for row in matrix[: self.settings.analysis.max_faces]:
            x, y, w, h = (float(value) for value in row[:4])
            if min(w, h) < self.settings.recognition.min_face_pixels:
                continue
            landmarks = tuple((float(row[index]), float(row[index + 1])) for index in range(4, 14, 2))
            observations.append(
                FaceObservation(
                    bbox=(x, y, w, h),
                    landmarks=landmarks,
                    detector_confidence=float(row[14]),
                    raw=np.asarray(row, dtype=np.float32),
                )
            )
        return observations

    def align(self, image: np.ndarray, face: FaceObservation) -> np.ndarray:
        if not self.ready:
            raise RuntimeError("recognition model unavailable")
        return self._recognizer.alignCrop(image, face.raw)

    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        if not self.ready:
            raise RuntimeError("recognition model unavailable")
        vector = np.asarray(self._recognizer.feature(aligned_face), dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            raise RuntimeError("recognizer produced a zero embedding")
        return vector / norm


def load_bgr(path: Path) -> np.ndarray:
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"unable to decode frame {path.name}")
    return image

