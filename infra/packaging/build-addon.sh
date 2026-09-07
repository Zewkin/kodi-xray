#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
VERSION="0.1.0"
OUTPUT="$ROOT/dist/script.kodi.xray-$VERSION.zip"
mkdir -p "$ROOT/dist"
cd "$ROOT/kodi-addon"
zip -qr "$OUTPUT" script.kodi.xray -x '*/__pycache__/*' '*.pyc'
echo "$OUTPUT"

