# Security

- The API is reachable only on the new LXC's LAN address and nftables allows
  port 8787 only from the routed private LANs `10.42.42.0/24`,
  `10.21.21.0/24`, and `192.168.1.0/24`.
- Functional API calls use a random 256-bit bearer token. The backend token is
  in `/etc/xray/xray.env` mode 0600 and is not logged or committed.
- The LXC is unprivileged. `/media` is a read-only Proxmox bind; the container
  has no NFS-mount capability and no Proxmox credentials.
- systemd runs both services as the locked `xray` user with an empty capability
  set, `NoNewPrivileges`, restricted address families and a private umask. The
  mount-namespace hardening flags that fail inside unprivileged LXC are not used.
- URL decoding, traversal rejection, canonical `realpath`, allow-listed roots
  and regular-file checks prevent arbitrary reads through media mapping.
- Reference downloads require HTTPS and reject loopback/private/link-local
  destinations. Content type and size are checked.
- Frames are temporary under `/run/xray`; embeddings and authorization headers
  are never logged. Background whole-library indexing defaults to disabled.
- The service exposes no general photo upload or global-celebrity endpoint.

Face embeddings are biometric data. Keep the LXC and Kodi settings private,
limit backups appropriately, and follow applicable consent/privacy law.
