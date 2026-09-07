#!/bin/sh
set -eu
CTID="${XRAY_CTID:-113}"
BUNDLE="${1:?usage: update.sh /path/to/kodi-xray.tar.gz}"
pct push "$CTID" "$BUNDLE" /root/kodi-xray.tar.gz
pct exec "$CTID" -- sh -c 'systemctl stop xray-worker xray-api; tar -xzf /root/kodi-xray.tar.gz -C /opt/xray --strip-components=1; rm /root/kodi-xray.tar.gz; /opt/xray/.venv/bin/pip install --upgrade /opt/xray; if [ -L /usr/local/bin/xrayctl ]; then unlink /usr/local/bin/xrayctl; fi; install -m 0755 /opt/xray/infra/bin/xrayctl /usr/local/bin/xrayctl; install -m 0644 /opt/xray/infra/config/nftables.conf /etc/nftables.conf; install -m 0644 /opt/xray/infra/systemd/xray-*.service /etc/systemd/system/; systemctl daemon-reload; systemctl enable xray-firewall.service; systemctl restart xray-firewall xray-api xray-worker; chmod 0640 /var/lib/xray/xray.db 2>/dev/null || true'
