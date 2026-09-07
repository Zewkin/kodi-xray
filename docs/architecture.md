# Architecture

The system has three deliberately separate layers:

1. The backend resolves a configured NFS URL, extracts three short-lived
   frames, detects/alines faces, compares embeddings with the current cast and
   returns normalized source-frame boxes.
2. The addon's layout engine maps normalized boxes into the active Kodi video
   viewport and chooses placements while avoiding faces, subtitles and
   skin-owned regions.
3. A skin adapter supplies visibility, safe-area and visual theme semantics.

The API and gallery worker are separate systemd services. Both use the same
SQLite database in WAL mode. The worker runs at low CPU/I/O priority; no
whole-library job exists in the default configuration. Model weights and
application state live outside Git.

Frames exist only below `/run/xray/analysis-*` and are removed in a `finally`
block. The default deployment gives `/media` to the LXC through a Proxmox
read-only bind mount.

