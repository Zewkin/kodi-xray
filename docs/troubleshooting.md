# Troubleshooting

Run `xrayctl doctor`, then `xrayctl health`. Inspect services with
`systemctl status xray-firewall xray-api xray-worker` and logs with
`journalctl -u xray-firewall -u xray-api -u xray-worker`.

- `401`: Kodi token does not match `/etc/xray/xray.env`.
- `422 path does not match`: add the exact Kodi NFS prefix to `path_maps`; do
  not broaden `media.roots`.
- `/ready` reports model missing: rerun `install-models.sh` and verify its
  hashes/manifest.
- Gallery stays empty: Kodi/TMDb supplied no public HTTPS cast images, or
  validation rejected them. Check worker logs without enabling frame storage.
- HDR extraction fails: ensure ffmpeg has `zscale`; the extractor retries the
  frame without tone mapping, which is usable but may reduce recognition.
- Kodi overlay disappears: an incompatible OSD is open, playback resumed, or a
  seek invalidated the result. This is deliberate stale-state protection.
- Non-linear stretch shows a side panel: exact face anchoring is intentionally
  disabled in that mode.
