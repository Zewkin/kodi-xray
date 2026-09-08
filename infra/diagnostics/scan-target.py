#!/usr/bin/env python3
"""Find strong gallery matches for one actor in a bounded video interval."""

from __future__ import annotations

import argparse
import json

import cv2
import numpy as np

from xray.config import load_settings
from xray.db import Database
from xray.recognition import OpenCvSFaceBackend


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("media_match")
    parser.add_argument("target_external_id")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--step", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    settings = load_settings()
    database = Database(settings.database.path)
    recognizer = OpenCvSFaceBackend(settings)
    with database.connect() as connection:
        row = connection.execute(
            "SELECT id, path, duration FROM media WHERE path LIKE ? ORDER BY updated_at DESC LIMIT 1",
            ("%" + args.media_match + "%",),
        ).fetchone()
    if row is None:
        raise SystemExit("matching media was not found")
    gallery = database.gallery_for_media(
        int(row["id"]), recognizer.model_id, recognizer.model_version
    )
    targets = [entry for entry in gallery if entry["external_id"] == args.target_external_id]
    if not targets:
        raise SystemExit("target has no gallery embedding")

    cap = cv2.VideoCapture(row["path"])
    end = min(float(row["duration"]), args.end or float(row["duration"]))
    results = []
    position = max(0.0, args.start)
    try:
        while position <= end:
            cap.set(cv2.CAP_PROP_POS_MSEC, position * 1000.0)
            ok, image = cap.read()
            if ok and image is not None:
                height, width = image.shape[:2]
                if width > settings.media.max_decode_width:
                    scale = settings.media.max_decode_width / width
                    image = cv2.resize(image, (round(width * scale), round(height * scale)))
                for face in recognizer.detect(image):
                    vector = recognizer.embed(recognizer.align(image, face))
                    scores = sorted(
                        (
                            (float(np.dot(vector, entry["vector"])), entry["name"])
                            for entry in gallery
                        ),
                        reverse=True,
                    )
                    target_score = max(
                        float(np.dot(vector, entry["vector"])) for entry in targets
                    )
                    results.append(
                        {
                            "timestamp": round(position, 3),
                            "target_similarity": round(target_score, 4),
                            "best": scores[0][1],
                            "best_similarity": round(scores[0][0], 4),
                            "margin": round(scores[0][0] - scores[1][0], 4),
                            "bbox": [round(value, 1) for value in face.bbox],
                            "confidence": round(face.detector_confidence, 4),
                        }
                    )
            position += args.step
    finally:
        cap.release()
    results.sort(key=lambda item: item["target_similarity"], reverse=True)
    print(json.dumps(results[: args.limit], indent=2))


if __name__ == "__main__":
    main()
