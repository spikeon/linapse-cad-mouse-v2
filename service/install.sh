#!/bin/bash
# CAD Mouse MK2 — Linux integration installer
# Tested on Arch Linux (Wayland). Should work on any systemd distro.
set -e
USER="${USER:-$(whoami)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_BIN="$HOME/.local/bin"
SYSTEMD_USER="$HOME/.config/systemd/user"

err() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }
section() { echo; echo "==> $*"; }

# ── Prerequisites ────────────────────────────────────────────────────────────
section "Checking prerequisites"

command -v python3 >/dev/null || err "python3 not found"

command -v ydotool >/dev/null || err "ydotool not found. Install via your package manager."
command -v systemctl >/dev/null || err "systemd not found"

info "All prerequisites found."

# Detect package manager.
if   command -v pacman >/dev/null; then PM=pacman
elif command -v apt-get >/dev/null; then PM=apt
elif command -v dnf    >/dev/null; then PM=dnf
else PM=""; fi

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

# ── Input group ──────────────────────────────────────────────────────────────
section "Adding $USER to 'input' group"

if groups | grep -qw input; then
    info "Already in 'input' group."
else
    sudo usermod -aG input "$USER"
    info "Added. You must log out and back in (or reboot) before buttons will work."
fi

# ── linapse-service script ────────────────────────────────────────────────────
section "Installing linapse-service"

pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || \
    pip3 install --break-system-packages websockets fastapi "uvicorn[standard]" numpy scipy 2>/dev/null || true
python3 -c "import websockets, fastapi, uvicorn, numpy, scipy" || err "Python browser-bridge dependencies install failed"

mkdir -p "$USER_BIN"
cp "$SCRIPT_DIR/linapse-service" "$USER_BIN/linapse-service"
chmod +x "$USER_BIN/linapse-service"
cp -r "$SCRIPT_DIR/linapse" "$USER_BIN/"
cp -r "$SCRIPT_DIR/spacenav_ws" "$USER_BIN/"
cp "$SCRIPT_DIR/linapse-ws-proxy" "$USER_BIN/linapse-ws-proxy"
chmod +x "$USER_BIN/linapse-ws-proxy"
info "Installed to $USER_BIN/linapse-service and $USER_BIN/linapse-ws-proxy"

# Disable old spnav-buttons if it was installed
systemctl --user disable --now spnav-buttons 2>/dev/null || true

# ── systemd user services ────────────────────────────────────────────────────
section "Installing systemd user services"

mkdir -p "$SYSTEMD_USER"
for svc in ydotoold linapse-service; do
    cp "$SCRIPT_DIR/systemd/${svc}.service" "$SYSTEMD_USER/"
    info "Copied ${svc}.service"
done

# Disable legacy spacenav-ws service (browser bridge is built into linapse-service)
systemctl --user disable --now spacenav-ws 2>/dev/null || true

systemctl --user import-environment PATH || true
systemctl --user daemon-reload
systemctl --user enable --now ydotoold linapse-service
info "Services enabled and started."

# ── Application Launcher Menu Shortcut ────────────────────────────────────────
section "Installing application launcher shortcut"

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

# Resolve absolute path to repo directory (one level up from SCRIPT_DIR)
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Replace repository path in template and write to target
sed -e "s|__REPO_DIR__|$REPO_ROOT|g" \
    "$SCRIPT_DIR/systemd/linapse-configurator.desktop" \
    > "$DESKTOP_DIR/linapse-configurator.desktop"

chmod +x "$DESKTOP_DIR/linapse-configurator.desktop"
info "Installed launcher shortcut to $DESKTOP_DIR/linapse-configurator.desktop"

# ── Environment Setup ────────────────────────────────────────────────────────
section "Configuring user systemd environment for native applications"

mkdir -p "$HOME/.config/environment.d"
cat <<'EOF' > "$HOME/.config/environment.d/99-spnav.conf"
SPNAV_SOCKET="${XDG_RUNTIME_DIR}/spnav.sock"
EOF
info "Environment configuration file written to ~/.config/environment.d/99-spnav.conf"


# ── udev rules ───────────────────────────────────────────────────────────────
section "Installing udev rules for device permissions"

if [ -f "$SCRIPT_DIR/udev/99-spacemouse.rules" ]; then
    if [ -f /etc/udev/rules.d/99-spacemouse.rules ] && cmp -s "$SCRIPT_DIR/udev/99-spacemouse.rules" /etc/udev/rules.d/99-spacemouse.rules; then
        info "udev rules already up to date."
    else
        sudo cp "$SCRIPT_DIR/udev/99-spacemouse.rules" /etc/udev/rules.d/99-spacemouse.rules
        info "Copied udev rules to /etc/udev/rules.d/"
        sudo udevadm control --reload-rules 2>/dev/null || info "Warning: Could not reload udev rules"
        sudo udevadm trigger --action=add 2>/dev/null || info "Warning: Could not trigger udev rules"
    fi
else
    err "udev rules file not found"
fi


# ── Browser extension ─────────────────────────────────────────────────────────
section "Installing Linapse Browser Connector browser extension"

chmod +x "$SCRIPT_DIR/../extension/scripts/install-linux.sh"
"$SCRIPT_DIR/../extension/scripts/install-linux.sh" || info "Browser extension setup printed above."


# ── Done ─────────────────────────────────────────────────────────────────────
section "Done!"
cat <<'EOF'

Next steps:
  1. Install the Linapse Browser Connector from your browser's extension store (links above).
  2. Visit https://cad.onshape.com or SketchUp Web and open any document.
  3. Move the CAD Mouse — the viewport should respond.

If the mouse was already plugged in before installing, unplug and replug it.
For detailed setup guides for 14 apps (Blender, FreeCAD, Unreal, Unity, etc.), see docs/INTEGRATIONS.md.
You must log out and back in (or reboot) to apply the systemd environment socket configuration for native applications.
If buttons don't work, log out and back in (or reboot) so the 'input' group takes effect.
EOF

