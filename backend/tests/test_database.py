from pathlib import Path

from xray.db import Database


def test_cache_roundtrip_and_wal(tmp_path):
    media = tmp_path / "movie.mkv"
    media.write_bytes(b"not-real-video")
    database = Database(tmp_path / "xray.db")
    database.initialize()
    media_id = database.upsert_media("key", media, 120.0, {"title": "Movie"})
    response = {"people": [], "unknown_faces": 0}
    database.put_analysis(media_id, 12.5, 25, "model", response, 99.0)
    assert database.get_cached(media_id, 25, "model") == response
    with database.connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_detection_persistence_and_invalidation(tmp_path):
    media = tmp_path / "movie.mkv"
    media.write_bytes(b"not-real-video")
    database = Database(tmp_path / "xray.db")
    database.initialize()
    media_id = database.upsert_media("key", media, 120.0, {"title": "Movie"})
    person_id = database.upsert_person("tmdb:1", "Actor")
    database.set_roles(media_id, person_id, ["Role"])
    response = {
        "people": [
            {
                "actor": {"id": "tmdb:1", "name": "Actor"},
                "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
                "similarity": 0.75,
                "top2_margin": 0.2,
                "accepted": True,
            }
        ],
        "unknown_faces": 0,
    }
    database.put_analysis(media_id, 12.5, 25, "model", response, 99.0)
    assert database.stats()["detections"] == 1
    assert database.invalidate_media("key") == 1
    assert database.stats()["detections"] == 0
