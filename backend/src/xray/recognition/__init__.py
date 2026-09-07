from .backend import FaceObservation, FaceRecognitionBackend, OpenCvSFaceBackend
from .matching import MatchResult, match_embedding

__all__ = [
    "FaceObservation",
    "FaceRecognitionBackend",
    "MatchResult",
    "OpenCvSFaceBackend",
    "match_embedding",
]

