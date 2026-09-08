#!/usr/bin/env python3
"""Score every detected face in a frame against one media gallery."""

from __future__ import annotations

import argparse
import json

import numpy as np

from xray.config import load_settings
from xray.db import Database
from xray.recognition import OpenCvSFaceBackend
from xray.recognition.backend import load_bgr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("media_match")
    args = parser.parse_args()

    settings = load_settings()
    database = Database(settings.database.path)
    recognizer = OpenCvSFaceBackend(settings)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT id, path FROM media WHERE path LIKE ? ORDER BY updated_at DESC LIMIT 1",
            ("%" + args.media_match + "%",),
        ).fetchone()
    if row is None:
        raise SystemExit("matching media was not found")
    gallery = database.gallery_for_media(
        int(row["id"]), recognizer.model_id, recognizer.model_version
    )
    image = load_bgr(args.image)
    detections = []
    for face in recognizer.detect(image):
        vector = recognizer.embed(recognizer.align(image, face))
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
        detections.append(
            {
                "bbox": [round(value, 1) for value in face.bbox],
                "confidence": round(face.detector_confidence, 4),
                "top": scores[:5],
            }
        )
    print(
        json.dumps(
            {
                "image": args.image,
                "shape": [int(value) for value in image.shape[:2]],
                "media": row["path"],
                "gallery_entries": len(gallery),
                "faces": detections,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
