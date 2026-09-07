# Kodi X-Ray

Kodi X-Ray is a local, LAN-only face-to-cast recognizer for Kodi 21/22. When
playback is paused, the addon sends only the media path and timestamp to a
self-hosted backend. The backend reads the same media file, extracts temporary
frames, compares detected faces only with the current title's cast, and returns
normalized face coordinates. The Kodi addon renders a transparent overlay and
closes it immediately on resume.

Version `0.1.0` provides:

- a FastAPI backend, SQLite WAL cache, gallery worker and `xrayctl`;
- secure configurable NFS path mapping and short-lived frame extraction;
- pluggable face recognition with OpenCV YuNet + SFace as the baseline;
- conservative threshold-and-margin matching with multi-frame evidence;
- a pure-Python Kodi addon with generic and Pellucid adapters;
- reproducible unprivileged Proxmox LXC provisioning and rollback tooling.

The backend never uploads frames or embeddings. It has no OpenAI or cloud AI
dependency. TMDb is optional and is used only for cast metadata/reference
images when an operator supplies a token.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
cp infra/config/xray.example.yaml /tmp/xray.yaml
XRAY_CONFIG=/tmp/xray.yaml XRAY_API_TOKEN=development-only-token \
  .venv/bin/uvicorn xray.api.app:app --reload
.venv/bin/pytest
```

Models are deliberately excluded from Git. See
[`docs/recognition.md`](docs/recognition.md) and
[`infra/provisioning/install-models.sh`](infra/provisioning/install-models.sh).

Deployment and rollback are documented in
[`docs/deployment.md`](docs/deployment.md) and
[`docs/uninstall.md`](docs/uninstall.md).

