from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import numpy as np

from xray.config import Settings
from xray.db import Database
from xray.metadata import MetadataProvider
from xray.recognition import FaceRecognitionBackend


class GalleryBuilder:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        recognizer: FaceRecognitionBackend,
        metadata: MetadataProvider,
    ):
        self.settings = settings
        self.database = database
        self.recognizer = recognizer
        self.metadata = metadata
        self.portrait_dir = database.path.parent / "portraits"

    def run_one(self) -> bool:
        job = self.database.claim_gallery_job()
        if not job:
            return False
        try:
            if not self.recognizer.ready:
                raise RuntimeError("recognition model is not ready")
            person = self.database.person(int(job["person_id"]))
            if not person:
                raise RuntimeError("gallery person no longer exists")
            wanted = self.settings.metadata.reference_images_per_actor
            existing = self.database.count_embeddings(
                int(job["person_id"]), self.recognizer.model_id, self.recognizer.model_version
            )
            if existing >= wanted:
                self.database.finish_gallery_job(int(job["id"]))
                return True
            urls = list(dict.fromkeys(json.loads(job["urls_json"])))
            urls.extend(url for url in self.metadata.get_person_images(person["external_id"]) if url not in urls)
            existing_sources = self.database.embedding_sources(
                int(job["person_id"]), self.recognizer.model_id, self.recognizer.model_version
            )
            urls = [url for url in urls if url not in existing_sources]
            successes = 0
            for url in urls:
                if existing + successes >= wanted:
                    break
                image = self._download(url)
                face, quality, inference_image = self._select_reference_face(image)
                if face is None:
                    continue
                aligned = self.recognizer.align(inference_image, face)
                vector = self.recognizer.embed(aligned)
                self.database.add_embedding(
                    int(job["person_id"]),
                    vector,
                    self.recognizer.model_id,
                    self.recognizer.model_version,
                    url,
                    quality,
                )
                if not person.get("portrait_path"):
                    self._store_portrait(int(job["person_id"]), person["external_id"], image)
                    person["portrait_path"] = "stored"
                successes += 1
            if existing + successes == 0:
                raise RuntimeError("no valid reference faces were available")
            self.database.finish_gallery_job(int(job["id"]))
        except Exception as exc:
            self.database.finish_gallery_job(int(job["id"]), str(exc))
        return True

    def _download(self, url: str) -> np.ndarray:
        import cv2

        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError("reference image URL must be public HTTPS")
        self._reject_private_host(parsed.hostname)
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "Kodi-XRay/0.1"})
            response.raise_for_status()
            final_url = response.url
            if final_url.scheme != "https" or not final_url.host:
                raise RuntimeError("reference image redirect must remain on public HTTPS")
            self._reject_private_host(final_url.host)
            if len(response.content) > 10 * 1024 * 1024:
                raise RuntimeError("reference image exceeds 10 MiB")
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise RuntimeError("reference URL did not return an image")
        image = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError("reference image could not be decoded")
        return image

    @staticmethod
    def _reject_private_host(hostname: str) -> None:
        if hostname.casefold() == "localhost":
            raise RuntimeError("private reference hosts are not allowed")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise RuntimeError("reference host could not be resolved") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise RuntimeError("private reference hosts are not allowed")

    def _select_reference_face(self, image: np.ndarray):
        inference_image = image
        height, width = image.shape[:2]
        if max(height, width) > 960:
            import cv2

            scale = 960.0 / max(height, width)
            inference_image = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        faces = self.recognizer.detect(inference_image)
        if not faces:
            return None, 0.0, inference_image
        height, width = inference_image.shape[:2]
        ranked = sorted(
            faces,
            key=lambda face: face.bbox[2] * face.bbox[3] * face.detector_confidence,
            reverse=True,
        )
        best = ranked[0]
        area_ratio = best.bbox[2] * best.bbox[3] / (width * height)
        if area_ratio < 0.015:
            return None, 0.0, inference_image
        if len(ranked) > 1:
            best_area = best.bbox[2] * best.bbox[3]
            second_area = ranked[1].bbox[2] * ranked[1].bbox[3]
            if second_area >= best_area * 0.70:
                return None, 0.0, inference_image
        gray = inference_image.mean(axis=2)
        sharpness = float(np.var(np.diff(gray, axis=0)))
        if sharpness < 8.0:
            return None, 0.0, inference_image
        quality = min(1.0, best.detector_confidence * min(1.0, area_ratio / 0.08))
        return best, quality, inference_image

    def _store_portrait(self, person_id: int, external_id: str, image: np.ndarray) -> None:
        import cv2

        safe_name = "".join(character if character.isalnum() else "_" for character in external_id)
        self.portrait_dir.mkdir(parents=True, exist_ok=True, mode=0o750)
        target = self.portrait_dir / f"{safe_name}.jpg"
        cv2.imwrite(str(target), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        target.chmod(0o640)
        self.database.set_portrait(person_id, target)
