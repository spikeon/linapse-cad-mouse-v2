#!/bin/bash
# Linapse — CAD Mouse MK2 full setup
#
# Front door for setting up the entire stack on a fresh machine:
#   1. install distro packages (ydotool)
#   2. (optional) flash the firmware            --flash
#   3. install the host integration             service/install.sh
#   4. install + enable the configurator service
#   5. install the browser extension
#
# Usage:
#   ./setup.sh                 # packages + host + configurator
#   ./setup.sh --flash         # also build & flash firmware first
#   ./setup.sh --port 7890     # configurator port (default 7890)
#   ./setup.sh --yes           # don't prompt before installing packages
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_USER="$HOME/.config/systemd/user"
CONFIGURATOR_DIR="$REPO_DIR/configurator"

DO_FLASH=0
ASSUME_YES=0
PORT=7890

err()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }
section() { echo; echo "######## $*"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --flash) DO_FLASH=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --port) shift; PORT="$1" ;;
        --port=*) PORT="${1#*=}" ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) err "Unknown argument: $1" ;;
    esac
    shift
done

[[ "$PORT" =~ ^[0-9]+$ ]] || err "--port must be a number"

# ── 1. Distro packages ────────────────────────────────────────────────────────
section "1. Distro packages"

# Detect package manager.
if   command -v pacman >/dev/null; then PM=pacman
elif command -v apt-get >/dev/null; then PM=apt
elif command -v dnf    >/dev/null; then PM=dnf
else PM=""; fi
[ -n "$PM" ] && info "Detected package manager: $PM" || info "No supported package manager detected (pacman/apt/dnf)."

# Stop and disable active or enabled spacenavd service
if systemctl is-active --quiet spacenavd 2>/dev/null || systemctl is-enabled --quiet spacenavd 2>/dev/null; then
    info "Stopping and disabling active/enabled spacenavd service..."
    sudo systemctl stop spacenavd || true
    sudo systemctl disable spacenavd || true
fi

# Uninstall spacenavd package if installed
if [ -n "$PM" ]; then
    has_spacenavd=0
    case "$PM" in
        pacman) pacman -Qi spacenavd >/dev/null 2>&1 && has_spacenavd=1 ;;
        apt)    dpkg -l spacenavd >/dev/null 2>&1 && has_spacenavd=1 ;;
        dnf)    rpm -q spacenavd >/dev/null 2>&1 && has_spacenavd=1 ;;
    esac
    if [ "$has_spacenavd" -eq 1 ]; then
        info "Uninstalling spacenavd package..."
        case "$PM" in
            pacman) sudo pacman -Rns --noconfirm spacenavd || true ;;
            apt)    sudo apt-get remove -y spacenavd || true ;;
            dnf)    sudo dnf remove -y spacenavd || true ;;
        esac
    fi
fi

# ydotool comes from the distro repos.
missing=()
command -v ydotool   >/dev/null || missing+=(ydotool)

install_pkgs() {
    [ ${#missing[@]} -eq 0 ] && { info "ydotool already installed."; return; }
    echo "  Will install: ${missing[*]}"
    if [ "$ASSUME_YES" -eq 0 ]; then
        read -rp "  Install these with sudo $PM? [y/N] " ans
        [[ "$ans" =~ ^[Yy]$ ]] || err "Declined. Install ${missing[*]} manually and re-run."
    fi
    case "$PM" in
        pacman) sudo pacman -S --needed "${missing[@]}" ;;
        apt)    sudo apt-get update && sudo apt-get install -y "${missing[@]}" ;;
        dnf)    sudo dnf install -y "${missing[@]}" ;;
        *)      err "No supported package manager. Install manually: ${missing[*]}" ;;
    esac
}
install_pkgs

# ── 2. Firmware (optional) ─────────────────────────────────────────────────────
if [ "$DO_FLASH" -eq 1 ]; then
    section "2. Firmware"
    bash "$REPO_DIR/service/flash.sh"
else
    section "2. Firmware (skipped)"
    info "Run with --flash to build and flash, or flash manually. See README.md."
fi

# ── 3. Host integration ────────────────────────────────────────────────────────
section "3. Host integration (service/install.sh)"
( cd "$REPO_DIR/service" && chmod +x install.sh && ./install.sh )

# ── 4. Configurator service ────────────────────────────────────────────────────
section "4. Configurator service (port $PORT)"

[ -f "$CONFIGURATOR_DIR/index.html" ] || err "configurator/index.html not found at $CONFIGURATOR_DIR"
mkdir -p "$SYSTEMD_USER"
sed -e "s|__CONFIGURATOR_DIR__|$CONFIGURATOR_DIR|g" \
    -e "s|__PORT__|$PORT|g" \
    "$REPO_DIR/service/systemd/linapse-configurator.service" \
    > "$SYSTEMD_USER/linapse-configurator.service"
systemctl --user daemon-reload
systemctl --user enable --now linapse-configurator
info "Serving $CONFIGURATOR_DIR at http://localhost:$PORT"

cat <<EOF

######## Done

  Configurator:  http://localhost:$PORT   (see docs/USAGE.md)
  Integrations:  docs/INTEGRATIONS.md     (Blender, FreeCAD, Maya, Unreal, Unity setup)
  You must log out and back in (or reboot) to apply the systemd environment socket configuration for native applications.
  If buttons don't work, log out and back in so the 'input' group takes effect.
  If the device was plugged in before install, unplug and replug it.
EOF

