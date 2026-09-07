# Deployment report

Status at 2026-09-07: backend deployed and live-tested; Kodi client install and
visual acceptance remain operator/client-side steps.

## Installed topology

- Proxmox VE `8.4.16`; no reboot, routing, NAS, export, or existing-guest
  changes were made.
- New unprivileged LXC `113`, hostname `xray-backend`, static
  `10.42.42.6/24`, on-boot startup order 4.
- 6 vCPU visible with `cpulimit=4`, 8 GiB RAM, 2 GiB swap, and 32 GiB root on
  `nvme1-lvm`.
- Host `/mnt/bigdata/downloads` is bind-mounted at `/media` with `ro=1`; no
  duplicate NFS mount or host `/etc/fstab` entry was created.
- API `http://10.42.42.6:8787/api/v1`; nftables default-deny allows 8787 only
  from `10.42.42.0/24`, `10.21.21.0/24`, and `192.168.1.0/24`.
- Backend/addon/API/adapter versions: `0.1.0` / `0.1.0` / v1 / v1.
- `xray-api`, `xray-worker`, and boot-ordered `xray-firewall` are enabled and
  active as tested. API and worker run as locked user `xray` with no new
  privileges and empty capability sets.

Host configuration snapshots are under
`/var/lib/vz/xray-backups/20260907T183502Z/`. They are inventory/rollback
evidence; the snapshotted host files were not edited.

## Models and reference skin

- OpenCV YuNet `2023mar`, SHA-256
  `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
- OpenCV SFace `2021dec`, SHA-256
  `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`.
- CPU inference baseline; iGPU passthrough was deliberately not added.
- Pellucid reference commit
  `1394c02fc8b189263ae6abf1b1102b2a4d7bc7f1`; no optional skin patch is
  required or installed.

## Verification evidence

- Local automated suite: 14 tests passed; Python bytecode compilation, shell
  syntax, XML parsing, ZIP integrity, and secret scan passed.
- `/ready`: HTTP 200 from both inside the CT and routed client LAN.
- Missing bearer token: HTTP 401. Parent traversal attempt: HTTP 422.
- `xrayctl doctor`: media readable/not writable, DB, models, ffmpeg/ffprobe,
  free space, and disabled background indexing all passed.
- Real SDR scene, *The Judge* at 1200 s: Robert Downey Jr. accepted at cosine
  `0.8247`, top-two margin `0.6392`; cold latency `709.25 ms`.
- Same scene cache hit: `79.86 ms`.
- Four additional SDR samples accepted at cosine `0.5419`–`0.8247`; one
  uncertain scene remained Unknown rather than being force-labelled.
- Real DV/HDR unrelated scene tested against the two *The Judge* actors:
  `people=[]`, `unknown_faces=1`, cold latency `2727.48 ms`.
- Gallery jobs: 2/2 done on first retry-free run, two embeddings stored.
  Accepted detections persist in SQLite and temporary `/run/xray` frames are
  removed after analysis.
- Host load after the test burst was approximately `1.01 / 1.20 / 1.16`.

## Client handoff and known limits

The installable package is `dist/script.kodi.xray-0.1.0.zip` (SHA-256
`31bc0cfda2a30de3670e52b8c5a7b70aed22dedc8b36d8a70575822e28b77242`).
The reproducible deployment source bundle is `dist/kodi-xray-0.1.0.tar.gz`;
regenerate it with `infra/packaging/build-source.sh`. In each Kodi
client, install from ZIP, keep backend URL `http://10.42.42.6:8787`, copy the
token from `/etc/xray/xray.env`, and verify the exact NFS URL prefix used by
that client. The current allow-listed mappings cover the documented IP/host
forms; a different Kodi source prefix must be added explicitly.

Android/CoreELEC callback behavior and Pellucid/generic visual calibration
cannot be signed off without access to those live Kodi clients. HDR cold
analysis is slower than SDR on the CPU baseline (about 2.7 s in the tested
4K DV/HDR sample); cache hits remain fast.

## Rollback

Application-only rollback keeps the CT and all media intact:

```bash
infra/uninstall/uninstall.sh
```

Destroying only the dedicated CT is separately guarded:

```bash
XRAY_CONFIRM_DESTROY=113 infra/uninstall/uninstall.sh --destroy-container
```
