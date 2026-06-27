#!/bin/bash
set -e

REPO="topcug/secclear-cli"
INSTALL_DIR="/usr/local/bin"

get_latest_release() {
  curl -s "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/'
}

get_platform() {
  case "$(uname -s)" in
    Linux*)     echo "linux";;
    Darwin*)    echo "darwin";;
    *)          echo "unsupported"; exit 1;;
  esac
}

get_arch() {
  case "$(uname -m)" in
    x86_64)     echo "amd64";;
    aarch64)    echo "arm64";;
    arm64)      echo "arm64";;
    *)          echo "unsupported"; exit 1;;
  esac
}

main() {
  PLATFORM=$(get_platform)
  ARCH=$(get_arch)
  VERSION=$(get_latest_release)
  
  echo "Installing secclear $VERSION for $PLATFORM-$ARCH..."
  
  DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/secclear-$PLATFORM-$ARCH"
  TMP_FILE="/tmp/secclear"
  
  curl -sSL "$DOWNLOAD_URL" -o "$TMP_FILE"
  chmod +x "$TMP_FILE"
  
  if [ -w "$INSTALL_DIR" ]; then
    mv "$TMP_FILE" "$INSTALL_DIR/secclear"
  else
    echo "Need sudo to install to $INSTALL_DIR"
    sudo mv "$TMP_FILE" "$INSTALL_DIR/secclear"
  fi
  
  echo "secclear installed successfully!"
  echo "Run: secclear scan minikube"
}

main
