#!/bin/sh
set -eu
CTID="${XRAY_CTID:-113}"

if [ "${1:-}" = "--destroy-container" ]; then
  echo "Refusing implicit destruction. Set XRAY_CONFIRM_DESTROY=$CTID to confirm." >&2
  test "${XRAY_CONFIRM_DESTROY:-}" = "$CTID"
  pct stop "$CTID" || true
  pct destroy "$CTID" --purge 1
  echo "Destroyed X-Ray CT $CTID; media was a read-only bind and was not touched."
  exit 0
fi

pct exec "$CTID" -- sh -c 'systemctl disable --now xray-worker xray-api || true; rm -f /etc/systemd/system/xray-worker.service /etc/systemd/system/xray-api.service; systemctl daemon-reload; rm -rf /opt/xray /etc/xray /var/lib/xray'
echo "Removed X-Ray application from CT $CTID. The container and media remain intact."

