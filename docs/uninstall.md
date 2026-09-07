# Uninstall and rollback

Application-only removal keeps the dedicated CT and media intact:

```bash
infra/uninstall/uninstall.sh
```

Destroying the dedicated X-Ray CT is explicit and guarded:

```bash
XRAY_CONFIRM_DESTROY=113 infra/uninstall/uninstall.sh --destroy-container
```

The media bind is read-only and is removed with the CT config; no media file is
changed. No host NFS mount is created, so there is no `/etc/fstab` entry to
revert. Host inventory backups remain in `/var/lib/vz/xray-backups/`. There is
no Pellucid patch to undo in 0.1.0.

