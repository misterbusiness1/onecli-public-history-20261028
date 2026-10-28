#!/bin/sh
# Canonical OneCLI client installer. Server and CLI release channels are distinct.
set -eu
REPO="misterbusiness1/onecli"
BINARY="onecli"
WORK_DIR=""
STAGED_BINARY=""
cleanup() {
  [ -z "$WORK_DIR" ] || rm -rf "$WORK_DIR"
  [ -z "$STAGED_BINARY" ] || rm -f "$STAGED_BINARY"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
fetch() {
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$1" -o "$2"
}
main() {
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "$OS" in linux|darwin) ;; *) echo "Unsupported OS: $OS" >&2; exit 1 ;; esac
  ARCH=$(uname -m)
  case "$ARCH" in x86_64|amd64) ARCH=amd64 ;; arm64|aarch64) ARCH=arm64 ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; esac
  WORK_DIR=$(mktemp -d)
  VERSION="${ONECLI_CLI_VERSION:-}"
  if [ -z "$VERSION" ]; then
    fetch "https://raw.githubusercontent.com/$REPO/main/apps/cli/VERSION" "$WORK_DIR/VERSION"
    VERSION=$(tr -d '\r\n' < "$WORK_DIR/VERSION")
  fi
  VERSION=${VERSION#v}
  if ! printf '%s\n' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$'; then
    echo 'Invalid CLI version' >&2; exit 1
  fi
  ARCHIVE="onecli_${VERSION}_${OS}_${ARCH}.tar.gz"
  BASE_URL="https://github.com/$REPO/releases/download/cli%2Fv$VERSION"
  fetch "$BASE_URL/$ARCHIVE" "$WORK_DIR/$ARCHIVE"
  fetch "$BASE_URL/checksums.txt" "$WORK_DIR/checksums.txt"
  EXPECTED=$(awk -v name="$ARCHIVE" '$2 == name { print $1 }' "$WORK_DIR/checksums.txt")
  if ! printf '%s\n' "$EXPECTED" | grep -Eq '^[a-f0-9]{64}$'; then
    echo 'Missing or invalid archive checksum' >&2; exit 1
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL=$(sha256sum "$WORK_DIR/$ARCHIVE" | awk '{print $1}')
  elif command -v shasum >/dev/null 2>&1; then
    ACTUAL=$(shasum -a 256 "$WORK_DIR/$ARCHIVE" | awk '{print $1}')
  else
    echo 'sha256sum or shasum is required' >&2; exit 1
  fi
  if [ "$ACTUAL" != "$EXPECTED" ]; then
    echo 'CLI archive checksum mismatch; existing installation preserved' >&2; exit 1
  fi
  if ! tar -tzf "$WORK_DIR/$ARCHIVE" | awk '$0 != "onecli" && $0 != "LICENSE" {bad=1} END {exit bad}'; then
    echo 'Unexpected CLI archive entries' >&2; exit 1
  fi
  if ! tar -tvzf "$WORK_DIR/$ARCHIVE" | awk 'substr($0,1,1) != "-" {bad=1} END {exit bad}'; then
    echo 'CLI archive contains non-regular entries' >&2; exit 1
  fi
  tar -xzf "$WORK_DIR/$ARCHIVE" -C "$WORK_DIR"
  if [ ! -f "$WORK_DIR/$BINARY" ] || [ -L "$WORK_DIR/$BINARY" ]; then
    echo 'CLI archive does not contain a regular binary' >&2; exit 1
  fi
  if [ -n "${ONECLI_INSTALL_DIR:-}" ]; then
    INSTALL_DIR=$ONECLI_INSTALL_DIR
    mkdir -p "$INSTALL_DIR"
  elif [ -w /usr/local/bin ]; then
    INSTALL_DIR=/usr/local/bin
  else
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
  fi
  if [ -d "$INSTALL_DIR/$BINARY" ]; then
    echo 'CLI install target is a directory' >&2; exit 1
  fi
  STAGED_BINARY=$(mktemp "$INSTALL_DIR/.onecli-install.XXXXXX")
  cp "$WORK_DIR/$BINARY" "$STAGED_BINARY"
  chmod 755 "$STAGED_BINARY"
  # --help is local JSON and does not load operator credentials or contact a server.
  "$STAGED_BINARY" --help > "$WORK_DIR/help.json"
  ESCAPED_VERSION=$(printf '%s' "$VERSION" | sed 's/[.]/\\./g')
  if ! grep -Eq '"version"[[:space:]]*:[[:space:]]*"'"$ESCAPED_VERSION"'"' "$WORK_DIR/help.json"; then
    echo 'Downloaded CLI version does not match the release' >&2; exit 1
  fi
  mv -f "$STAGED_BINARY" "$INSTALL_DIR/$BINARY"
  STAGED_BINARY=""
  echo "Installed onecli $VERSION to $INSTALL_DIR/onecli"
  case ":$PATH:" in *":$INSTALL_DIR:"*) ;; *) echo "Add $INSTALL_DIR to PATH to use this installation." ;; esac
}
main
