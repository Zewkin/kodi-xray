#!/bin/sh
set -eu

CTID="${XRAY_CTID:-113}"
BUNDLE="${1:-/root/kodi-xray.tar.gz}"

if [ "$(id -u)" -ne 0 ]; then
  echo "deploy-container.sh must run as root on Proxmox" >&2
  exit 1
fi
test -f "$BUNDLE"
pct status "$CTID" | grep -q running

pct push "$CTID" "$BUNDLE" /root/kodi-xray.tar.gz
pct exec "$CTID" -- sh -c 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl ffmpeg nftables openssl python3 python3-pip python3-venv'
pct exec "$CTID" -- sh -c 'id xray >/dev/null 2>&1 || useradd --system --home /var/lib/xray --shell /usr/sbin/nologin xray'
pct exec "$CTID" -- sh -c 'install -d -m 0755 /opt/xray && tar -xzf /root/kodi-xray.tar.gz -C /opt/xray --strip-components=1 && rm /root/kodi-xray.tar.gz'
pct exec "$CTID" -- sh -c 'python3 -m venv /opt/xray/.venv && /opt/xray/.venv/bin/pip install --upgrade pip && /opt/xray/.venv/bin/pip install /opt/xray'
pct exec "$CTID" -- install -m 0755 /opt/xray/infra/bin/xrayctl /usr/local/bin/xrayctl
pct exec "$CTID" -- sh -c 'install -d -m 0750 -o xray -g xray /var/lib/xray /var/lib/xray/models /var/lib/xray/portraits /run/xray; install -d -m 0755 /etc/xray'
pct exec "$CTID" -- sh -c 'install -m 0644 /opt/xray/infra/config/xray.example.yaml /etc/xray/xray.yaml; if [ ! -f /etc/xray/xray.env ]; then umask 077; token=$(openssl rand -hex 32); printf "XRAY_API_TOKEN=%s\n" "$token" > /etc/xray/xray.env; fi; chmod 0600 /etc/xray/xray.env'
pct exec "$CTID" -- sh -c '/opt/xray/infra/provisioning/install-models.sh /var/lib/xray/models && chown -R xray:xray /var/lib/xray'
pct exec "$CTID" -- sh -c 'install -m 0644 /opt/xray/infra/systemd/xray-api.service /etc/systemd/system/xray-api.service; install -m 0644 /opt/xray/infra/systemd/xray-worker.service /etc/systemd/system/xray-worker.service'
pct exec "$CTID" -- sh -c 'install -m 0644 /opt/xray/infra/config/nftables.conf /etc/nftables.conf
systemctl enable --now nftables
systemctl daemon-reload
systemctl enable --now xray-firewall.service xray-api.service xray-worker.service
chmod 0640 /var/lib/xray/xray.db 2>/dev/null || true'

pct exec "$CTID" -- sh -c 'systemctl is-active xray-api.service; systemctl is-active xray-worker.service; findmnt /media; findmnt -no OPTIONS /media | tr "," "\n" | grep -qx ro; set -a; . /etc/xray/xray.env; set +a; runuser -u xray -- /opt/xray/.venv/bin/xrayctl doctor'
echo "Deployment complete in CT $CTID"
echo "Read the Kodi token locally with: pct exec $CTID -- sed -n 's/^XRAY_API_TOKEN=//p' /etc/xray/xray.env"
