#!/bin/sh
set -eu

CTID="${XRAY_CTID:-113}"
HOSTNAME="${XRAY_HOSTNAME:-xray-backend}"
IP_CIDR="${XRAY_IP_CIDR:-10.42.42.6/24}"
GATEWAY="${XRAY_GATEWAY:-10.42.42.1}"
NAMESERVER="${XRAY_NAMESERVER:-10.42.42.4}"
BRIDGE="${XRAY_BRIDGE:-vmbr0}"
STORAGE="${XRAY_STORAGE:-nvme1-lvm}"
TEMPLATE="${XRAY_TEMPLATE:-local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst}"
MEDIA_SOURCE="${XRAY_MEDIA_SOURCE:-/mnt/bigdata/downloads}"
BACKUP_ROOT="/var/lib/vz/xray-backups"

if [ "$(id -u)" -ne 0 ]; then
  echo "provision-host.sh must run as root" >&2
  exit 1
fi

echo "Phase 0 inventory"
pveversion
hostname
free -h
uptime
pvesm status
pct list
findmnt -T "$MEDIA_SOURCE"
test -d "$MEDIA_SOURCE"
test -r "$MEDIA_SOURCE"

if pct config "$CTID" >/dev/null 2>&1; then
  existing_hostname="$(pct config "$CTID" | awk '/^hostname:/ {print $2}')"
  if [ "$existing_hostname" != "$HOSTNAME" ]; then
    echo "CT $CTID already belongs to $existing_hostname; refusing to modify it" >&2
    exit 1
  fi
  echo "CT $CTID already exists; provisioning is idempotent"
else
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -m 0700 "$BACKUP_ROOT/$stamp"
  cp -a /etc/fstab "$BACKUP_ROOT/$stamp/fstab"
  cp -a /etc/network/interfaces "$BACKUP_ROOT/$stamp/interfaces"
  cp -a /etc/pve/storage.cfg "$BACKUP_ROOT/$stamp/storage.cfg"
  printf '%s\n' "$stamp" > "$BACKUP_ROOT/latest"

  pct create "$CTID" "$TEMPLATE" \
    --hostname "$HOSTNAME" \
    --unprivileged 1 \
    --cores 6 \
    --cpulimit 4 \
    --memory 8192 \
    --swap 2048 \
    --rootfs "$STORAGE:32" \
    --net0 "name=eth0,bridge=$BRIDGE,firewall=1,gw=$GATEWAY,ip=$IP_CIDR,type=veth" \
    --nameserver "$NAMESERVER" \
    --onboot 1 \
    --startup order=4,up=10 \
    --mp0 "$MEDIA_SOURCE,mp=/media,backup=0,ro=1" \
    --ostype debian
fi

if [ "$(pct status "$CTID" | awk '{print $2}')" != "running" ]; then
  pct start "$CTID"
fi

pct exec "$CTID" -- sh -c 'test -r /media && findmnt /media && ip -brief address'
echo "Provisioned CT $CTID ($HOSTNAME) at $IP_CIDR"

