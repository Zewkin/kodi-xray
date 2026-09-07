#!/bin/sh
set -eu

MODEL_DIR="${1:-/var/lib/xray/models}"
YUNET_NAME="face_detection_yunet_2023mar.onnx"
YUNET_SHA="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
YUNET_URL="https://huggingface.co/opencv/face_detection_yunet/resolve/main/$YUNET_NAME"
SFACE_NAME="face_recognition_sface_2021dec.onnx"
SFACE_SHA="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
SFACE_URL="https://huggingface.co/opencv/opencv_zoo/resolve/main/models/face_recognition_sface/$SFACE_NAME"

install -d -m 0750 "$MODEL_DIR"

download_verified() {
  name="$1"
  expected="$2"
  url="$3"
  target="$MODEL_DIR/$name"
  if [ -f "$target" ] && echo "$expected  $target" | sha256sum -c - >/dev/null 2>&1; then
    echo "$name already verified"
    return
  fi
  temporary="$target.download"
  curl --fail --location --retry 3 --connect-timeout 10 "$url" -o "$temporary"
  echo "$expected  $temporary" | sha256sum -c -
  chmod 0640 "$temporary"
  mv "$temporary" "$target"
}

download_verified "$YUNET_NAME" "$YUNET_SHA" "$YUNET_URL"
download_verified "$SFACE_NAME" "$SFACE_SHA" "$SFACE_URL"

downloaded_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$MODEL_DIR/manifest.json" <<EOF
{
  "provider": "OpenCV Zoo",
  "downloaded_at": "$downloaded_at",
  "models": [
    {
      "id": "opencv-yunet",
      "version": "2023mar",
      "file": "$YUNET_NAME",
      "sha256": "$YUNET_SHA",
      "source": "$YUNET_URL",
      "license": "MIT"
    },
    {
      "id": "opencv-sface",
      "version": "2021dec",
      "file": "$SFACE_NAME",
      "sha256": "$SFACE_SHA",
      "source": "$SFACE_URL",
      "license": "Apache-2.0"
    }
  ]
}
EOF
chmod 0640 "$MODEL_DIR/manifest.json"

