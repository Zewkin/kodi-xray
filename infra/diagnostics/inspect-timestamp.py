#!/usr/bin/env python3
"""Inspect detector confidence and gallery scores at one video timestamp."""

from __future__ import annotations

import argparse
import json

import numpy as np

from xray.config import load_settings
from xray.db import Database
from xray.media import FrameExtractor
from xray.recognition import OpenCvSFaceBackend
from xray.recognition.analyzer import SceneAnalyzer
from xray.recognition.backend import load_bgr
from xray.recognition.matching import match_embedding


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("media_match")
    parser.add_argument("timestamp", type=float)
    parser.add_argument("--thresholds", default="0.8,0.7,0.6,0.5")
    args = parser.parse_args()

    settings = load_settings()
    database = Database(settings.database.path)
    with database.connect() as connection:
        media = connection.execute(
            "SELECT id,path FROM media WHERE path LIKE ? ORDER BY updated_at DESC LIMIT 1",
            ("%" + args.media_match + "%",),
        ).fetchone()
    if media is None:
        raise SystemExit("matching media was not found")

    extractor = FrameExtractor(settings)
    probe = extractor.probe(media["path"])
    workspace, frames = extractor.extract(media["path"], args.timestamp, probe)
    image = load_bgr(frames[1])
    results = []
    try:
        for threshold in (float(value) for value in args.thresholds.split(",")):
            settings.recognition.detector_threshold = threshold
            recognizer = OpenCvSFaceBackend(settings)
            gallery = database.gallery_for_media(
                int(media["id"]), recognizer.model_id, recognizer.model_version
            )
            neighbor_faces = []
            for neighbor_image in (load_bgr(frames[0]), load_bgr(frames[2])):
                neighbor_faces.append(
                    [
                        (face, recognizer.embed(recognizer.align(neighbor_image, face)))
                        for face in recognizer.detect(neighbor_image)
                    ]
                )
            faces = []
            for face in recognizer.detect(image):
                vector = recognizer.embed(recognizer.align(image, face))
                central_match = match_embedding(
                    vector,
                    gallery,
                    settings.recognition.match_threshold,
                    settings.recognition.match_margin,
                )
                evidence = [vector]
                for observations in neighbor_faces:
                    candidate = SceneAnalyzer._temporal_candidate(
                        face, vector, observations, image.shape
                    )
                    if candidate is not None:
                        evidence.append(candidate)
                combined = np.mean(np.stack(evidence), axis=0)
                combined /= max(float(np.linalg.norm(combined)), 1e-12)
                match = match_embedding(
                    combined,
                    gallery,
                    settings.recognition.match_threshold,
                    settings.recognition.match_margin,
                )
                scores = sorted(
                    (
                        {
                            "name": entry["name"],
                            "role": entry["roles"],
                            "similarity": round(float(np.dot(vector, entry["vector"])), 4),
                        }
                        for entry in gallery
                    ),
                    key=lambda item: item["similarity"],
                    reverse=True,
                )
                faces.append(
                    {
                        "bbox": [round(value, 1) for value in face.bbox],
                        "confidence": round(face.detector_confidence, 4),
                        "evidence_frames": len(evidence),
                        "central_match": {
                            "name": central_match.person["name"] if central_match.person else None,
                            "best": round(central_match.best, 4),
                            "second": round(central_match.second, 4),
                            "margin": round(central_match.margin, 4),
                            "accepted": central_match.accepted,
                        },
                        "match": {
                            "name": match.person["name"] if match.person else None,
                            "best": round(match.best, 4),
                            "second": round(match.second, 4),
                            "margin": round(match.margin, 4),
                            "accepted": match.accepted,
                        },
                        "top": scores[:5],
                    }
                )
            results.append({"detector_threshold": threshold, "faces": faces})
    finally:
        extractor.cleanup(workspace)

    print(json.dumps({"timestamp": args.timestamp, "results": results}, indent=2))


if __name__ == "__main__":
    main()
