from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from xray.api.schemas import XRayRequest
from xray.config import Settings
from xray.db import Database
from xray.media import FrameExtractor, SecurePathResolver
from xray.recognition.backend import FaceObservation, FaceRecognitionBackend, load_bgr
from xray.recognition.matching import match_embedding


class SceneAnalyzer:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        resolver: SecurePathResolver,
        extractor: FrameExtractor,
        recognizer: FaceRecognitionBackend,
    ):
        self.settings = settings
        self.database = database
        self.resolver = resolver
        self.extractor = extractor
        self.recognizer = recognizer

    def analyze(self, request: XRayRequest) -> dict[str, Any]:
        started = time.monotonic()
        resolved = self.resolver.resolve(request.media.file)
        probe = self.extractor.probe(resolved.path)
        if request.playback.position > probe.duration + 1:
            raise ValueError("playback position exceeds media duration")
        media_key = resolved.media_key(probe.duration)
        media_id = self.database.upsert_media(
            media_key, resolved.path, probe.duration, request.media.model_dump(exclude={"cast"})
        )
        self._sync_cast(media_id, request.media.cast)
        bucket = round(request.playback.position / self.settings.analysis.cache_window_sec)
        cached = self.database.get_cached(media_id, bucket, self.recognizer.model_id)
        if cached:
            cached["cache_hit"] = True
            cached["latency_ms"] = round((time.monotonic() - started) * 1000, 2)
            return cached
        if not self.recognizer.ready:
            raise RuntimeError("face recognition model is unavailable")
        gallery = self.database.gallery_for_media(
            media_id, self.recognizer.model_id, self.recognizer.model_version
        )
        workspace, frame_paths = self.extractor.extract(resolved.path, request.playback.position, probe)
        try:
            images = [load_bgr(path) for path in frame_paths]
            central = images[1]
            central_faces = self.recognizer.detect(central)
            neighbor_faces = [self._embedded_faces(images[index]) for index in (0, 2)]
            people = []
            unknown = 0
            for face in central_faces:
                vector = self.recognizer.embed(self.recognizer.align(central, face))
                evidence = [vector]
                for observations in neighbor_faces:
                    candidate = self._temporal_candidate(face, vector, observations, central.shape)
                    if candidate is not None:
                        evidence.append(candidate)
                combined = np.mean(np.stack(evidence), axis=0)
                combined /= max(float(np.linalg.norm(combined)), 1e-12)
                match = match_embedding(
                    combined,
                    gallery,
                    self.settings.recognition.match_threshold,
                    self.settings.recognition.match_margin,
                )
                if not match.accepted or match.person is None:
                    unknown += 1
                    continue
                height, width = central.shape[:2]
                x, y, w, h = face.bbox
                people.append(
                    {
                        "actor": {"id": match.person["external_id"], "name": match.person["name"]},
                        "roles": match.person["roles"],
                        "bbox": {
                            "x": max(0.0, min(1.0, x / width)),
                            "y": max(0.0, min(1.0, y / height)),
                            "w": max(1 / width, min(1.0, w / width)),
                            "h": max(1 / height, min(1.0, h / height)),
                        },
                        "similarity": round(match.best, 4),
                        "top2_margin": round(match.margin, 4),
                        "accepted": True,
                    }
                )
            latency = round((time.monotonic() - started) * 1000, 2)
            response = {
                "timestamp": request.playback.position,
                "media_key": media_key,
                "frame": {"width": central.shape[1], "height": central.shape[0]},
                "people": people,
                "unknown_faces": unknown,
                "cache_hit": False,
                "latency_ms": latency,
            }
            self.database.put_analysis(media_id, request.playback.position, bucket, self.recognizer.model_id, response, latency)
            return response
        finally:
            self.extractor.cleanup(workspace)

    def _sync_cast(self, media_id: int, cast: list[Any]) -> None:
        from xray.metadata.providers import KodiMetadataProvider

        provider = KodiMetadataProvider()
        for item in cast:
            person = provider._person(item)
            person_id = self.database.upsert_person(person.external_id, person.name)
            self.database.set_roles(media_id, person_id, person.roles)
            self.database.enqueue_gallery(media_id, person_id, person.image_urls)

    def _embedded_faces(self, image: np.ndarray) -> list[tuple[FaceObservation, np.ndarray]]:
        result = []
        for face in self.recognizer.detect(image):
            result.append((face, self.recognizer.embed(self.recognizer.align(image, face))))
        return result

    @staticmethod
    def _temporal_candidate(
        central_face: FaceObservation,
        central_vector: np.ndarray,
        neighbors: list[tuple[FaceObservation, np.ndarray]],
        central_shape: tuple[int, ...],
    ) -> np.ndarray | None:
        if not neighbors:
            return None
        cx = central_face.bbox[0] + central_face.bbox[2] / 2
        cy = central_face.bbox[1] + central_face.bbox[3] / 2
        diagonal = float(np.hypot(central_shape[1], central_shape[0]))
        candidates = []
        for face, vector in neighbors:
            nx = face.bbox[0] + face.bbox[2] / 2
            ny = face.bbox[1] + face.bbox[3] / 2
            distance = float(np.hypot(cx - nx, cy - ny)) / diagonal
            similarity = float(np.dot(central_vector, vector))
            if distance <= 0.15 and similarity >= 0.30:
                candidates.append((similarity - distance, vector))
        return max(candidates, key=lambda pair: pair[0])[1] if candidates else None

