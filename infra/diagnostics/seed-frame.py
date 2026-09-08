#!/usr/bin/env python3
"""Add one human-verified media frame to an actor's local gallery."""

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
    parser.add_argument("target_external_id")
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    settings = load_settings()
    database = Database(settings.database.path)
    recognizer = OpenCvSFaceBackend(settings)
    with database.connect() as connection:
        media = connection.execute(
            "SELECT id, media_key, path FROM media WHERE path LIKE ? ORDER BY updated_at DESC LIMIT 1",
            ("%" + args.media_match + "%",),
        ).fetchone()
        person = connection.execute(
            "SELECT id, name FROM people WHERE external_id=?",
            (args.target_external_id,),
        ).fetchone()
    if media is None or person is None:
        raise SystemExit("matching media or person was not found")
    target_gallery = [
        item
        for item in database.gallery_for_media(
            int(media["id"]), recognizer.model_id, recognizer.model_version
        )
        if item["external_id"] == args.target_external_id
    ]
    if not target_gallery:
        raise SystemExit("target has no initial reference embedding")

    image = load_bgr(args.image)
    ranked = []
    for face in recognizer.detect(image):
        vector = recognizer.embed(recognizer.align(image, face))
        similarity = max(
            float(np.dot(vector, item["vector"])) for item in target_gallery
        )
        ranked.append((similarity, face, vector))
    if not ranked:
        raise SystemExit("no face was detected")
    similarity, face, vector = max(ranked, key=lambda item: item[0])
    if similarity < 0.30:
        raise SystemExit("best face is below the supervised seed safety floor")
    database.add_embedding(
        int(person["id"]),
        vector,
        recognizer.model_id,
        recognizer.model_version,
        args.source,
        face.detector_confidence,
        media_id=int(media["id"]),
        scope="media-specific",
    )
    print(
        json.dumps(
            {
                "person": person["name"],
                "media_key": media["media_key"],
                "source": args.source,
                "similarity_to_initial_reference": round(similarity, 4),
                "bbox": [round(value, 1) for value in face.bbox],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
