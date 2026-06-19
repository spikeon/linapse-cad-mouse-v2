#!/bin/bash
# CAD Mouse MK2 — firmware flasher
# Sets the spoofed USB VID/PID in platformio.ini, builds with PlatformIO, and
# copies the resulting UF2 onto the RP2040 once it is in BOOTSEL mode.
#
# Run from anywhere; paths are resolved relative to this script.
set -e
USER="${USER:-$(whoami)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INI="$REPO_DIR/platformio.ini"
ENV="seeed_xiao_rp2040"
UF2="$REPO_DIR/.pio/build/$ENV/firmware.uf2"

err()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }
section() { echo; echo "==> $*"; }

export PATH="$PATH:$HOME/.platformio/penv/bin"

command -v pio >/dev/null || err "PlatformIO (pio) not found. Install with: pipx install platformio  (or pip install platformio)"
[ -f "$INI" ] || err "platformio.ini not found at $INI"
# Read custom USB configuration if exists
ACTIONS_JSON="$HOME/.config/cad-mouse/actions.json"
if [ -f "$ACTIONS_JSON" ]; then
    USB_CONFIG=$(python3 -c "
import json
try:
    with open('$ACTIONS_JSON') as f:
        data = json.load(f)
        usb = data.get('custom_usb', {})
        if usb.get('enabled', False):
            print(f\"{usb.get('vid', '')} {usb.get('pid', '')}\")
except Exception:
    pass
" 2>/dev/null)
    if [ -n "$USB_CONFIG" ]; then
        read -r VID PID <<< "$USB_CONFIG"
        if [ -n "$VID" ] && [ -n "$PID" ]; then
            export LINAPSE_USB_VID="$VID"
            export LINAPSE_USB_PID="$PID"
            info "Applying custom USB override from actions.json: VID=$VID, PID=$PID"
        fi
    fi
fi

# ── Build ─────────────────────────────────────────────────────────────────────
section "Building firmware (pio run -e $ENV)"
( cd "$REPO_DIR" && pio run -e "$ENV" )
[ -f "$UF2" ] || err "Build finished but $UF2 not found"
info "Built $UF2"

# ── Stop Host Service ────────────────────────────────────────────────────────
if systemctl --user is-active --quiet linapse-service; then
    info "Stopping linapse-service..."
    systemctl --user stop linapse-service
    RESTART_SERVICE=1
else
    RESTART_SERVICE=0
fi

# ── Auto BOOTSEL reboot ──────────────────────────────────────────────────────
section "Rebooting device into BOOTSEL mode"
python3 -c "import serial, glob; p = (glob.glob('/dev/serial/by-id/usb-Seeed_Studio_CAD_Mouse*') + glob.glob('/dev/ttyACM*')); [serial.Serial(port, 1200).close() for port in p] if p else None" 2>/dev/null || true

# ── Wait and Mount ────────────────────────────────────────────────────────────
section "Locating RPI-RP2 drive"
target=""
device_node=""

for _ in $(seq 1 15); do
    # Check if already mounted
    for base in "/run/media/$USER" "/media/$USER" "/media" "/mnt"; do
        [ -d "$base/RPI-RP2" ] && target="$base/RPI-RP2" && break
    done
    [ -n "$target" ] && break

    # Try to locate block device by label
    device_node=$(lsblk -o PATH,LABEL | grep -w "RPI-RP2" | awk '{print $1}' | head -n 1 || true)
    if [ -n "$device_node" ] && command -v udisksctl >/dev/null; then
        info "Found RPI-RP2 block device at $device_node. Attempting to mount..."
        if udisksctl mount -b "$device_node" >/dev/null 2>&1; then
            sleep 1.5
            for base in "/run/media/$USER" "/media/$USER" "/media" "/mnt"; do
                [ -d "$base/RPI-RP2" ] && target="$base/RPI-RP2" && break
            done
            [ -n "$target" ] && break
        fi
    fi
    sleep 1
done

if [ -z "$target" ]; then
    echo "  Could not auto-reboot or mount automatically."
    echo "  Please put the device into BOOTSEL mode physically (hold B and tap R)."
    echo "  Waiting for RPI-RP2 drive to appear (Ctrl-C to abort)..."
    for _ in $(seq 1 60); do
        for base in "/run/media/$USER" "/media/$USER" "/media" "/mnt"; do
            [ -d "$base/RPI-RP2" ] && target="$base/RPI-RP2" && break
        done
        [ -n "$target" ] && break

        # Try mounting if block device appears
        device_node=$(lsblk -o PATH,LABEL | grep -w "RPI-RP2" | awk '{print $1}' | head -n 1 || true)
        if [ -n "$device_node" ] && command -v udisksctl >/dev/null; then
            if udisksctl mount -b "$device_node" >/dev/null 2>&1; then
                sleep 1.5
            fi
        fi
        sleep 1
    done
fi

[ -n "$target" ] || err "RPI-RP2 drive never appeared. Please mount it and copy $UF2 manually."
info "Found mount point: $target"

# ── Flash ─────────────────────────────────────────────────────────────────────
section "Copying firmware.uf2"
cp "$UF2" "$target/"
sync
info "Copied. Device is rebooting..."
sleep 3.5

# ── Restart Host Service ──────────────────────────────────────────────────────
if [ "$RESTART_SERVICE" -eq 1 ]; then
    section "Restarting host service"
    systemctl --user start linapse-service
    info "Service restarted."
fi

echo
info "Flashing complete and service is active!"
