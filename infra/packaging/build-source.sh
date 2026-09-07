#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
PARENT="$(dirname "$ROOT")"
NAME="$(basename "$ROOT")"
VERSION="0.1.0"
OUTPUT="$ROOT/dist/kodi-xray-$VERSION.tar.gz"
mkdir -p "$ROOT/dist"
COPYFILE_DISABLE=1 tar --no-xattrs \
  --exclude='./.git' --exclude='./dist' --exclude='__pycache__' --exclude='*.pyc' \
  -czf "$OUTPUT" -C "$PARENT" "$NAME"
echo "$OUTPUT"
