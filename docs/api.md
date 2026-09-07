# API v1

Base URL: `http://<backend>:8787/api/v1`. All functional endpoints require
`Authorization: Bearer <token>`. Authorization values are never logged.

`GET /health` reports process/dependency state and always answers while the API
is alive. `GET /ready` returns 200 only when DB, media, ffmpeg/ffprobe and the
models are ready; otherwise it returns 503.

`POST /api/v1/session/start` accepts client/Kodi/platform data plus the media
payload. It returns HTTP 202 after storing media/cast and queueing missing
gallery work; it does not wait for embeddings.

`POST /api/v1/xray` accepts:

```json
{
  "client_id": "living-room",
  "media": {
    "file": "nfs://10.42.42.3/mnt/bigdata/downloads/Movie.mkv",
    "media_type": "movie",
    "title": "Movie",
    "year": 2026,
    "unique_ids": {"tmdb": "123"},
    "cast": []
  },
  "playback": {"position": 4123.27}
}
```

The response contains `media_key`, timestamp, inference-frame dimensions,
accepted people, normalized boxes, similarity, top-two margin, unknown count,
cache state and latency. Unknown faces are counted but are not assigned to the
nearest actor.

`GET /api/v1/people/{id}/portrait` returns a cached portrait for themes that
use one. `GET /api/v1/metrics` returns counters and DB/cache sizes.

