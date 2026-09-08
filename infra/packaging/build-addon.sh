#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
VERSION="$(sed -n '/^<addon /s/.* version="\([^"]*\)".*/\1/p' "$ROOT/kodi-addon/script.kodi.xray/addon.xml")"
OUTPUT="$ROOT/dist/script.kodi.xray-$VERSION.zip"
mkdir -p "$ROOT/dist"
cd "$ROOT/kodi-addon"
zip -qr "$OUTPUT" script.kodi.xray -x '*/__pycache__/*' '*.pyc'
echo "$OUTPUT"
