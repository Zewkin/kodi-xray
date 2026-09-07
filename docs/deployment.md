# Deployment

On Proxmox, `provision-host.sh` inventories first and then creates CT 113 only
if that ID is unused. Defaults: unprivileged Debian 12, six visible CPUs,
`cpulimit=4`, 8 GiB RAM, 2 GiB swap, 32 GiB root on `nvme1-lvm`, static
`10.42.42.6/24`, and read-only `/mnt/bigdata/downloads` at `/media`.

Host `/etc/fstab`, network interfaces and storage config are copied to a
timestamped `/var/lib/vz/xray-backups/` directory before creation. The scripts
do not edit those files, NAS, existing guests, routing or firewall topology.

Create a source tarball, copy it to Proxmox, then run:

```bash
infra/packaging/build-source.sh
infra/provisioning/provision-host.sh
infra/provisioning/deploy-container.sh /root/kodi-xray.tar.gz
```

The deployer installs packages, application/models, a locked `xray` user,
systemd hardening, low-priority worker limits and a boot-ordered local
nftables rule. It prints a command for reading the Kodi token locally; the
token is not included in reports.

Operational checks and selective maintenance are available inside the CT:

```bash
xrayctl doctor
xrayctl status
xrayctl gallery status
xrayctl gallery rebuild --person tmdb:3223
xrayctl media list
xrayctl media invalidate <media-key>
```
