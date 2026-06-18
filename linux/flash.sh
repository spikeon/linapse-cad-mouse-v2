#!/bin/bash
# CAD Mouse MK2 — firmware flasher
# Sets the spoofed USB VID/PID in platformio.ini, builds with PlatformIO, and
# copies the resulting UF2 onto the RP2040 once it is in BOOTSEL mode.
#
# Run from anywhere; paths are resolved relative to this script.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INI="$REPO_DIR/platformio.ini"
ENV="seeed_xiao_rp2040"
UF2="$REPO_DIR/.pio/build/$ENV/firmware.uf2"

err()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }
section() { echo; echo "==> $*"; }

command -v pio >/dev/null || err "PlatformIO (pio) not found. Install with: pipx install platformio  (or pip install platformio)"
[ -f "$INI" ] || err "platformio.ini not found at $INI"



# ── Build ─────────────────────────────────────────────────────────────────────
section "Building firmware (pio run -e $ENV)"
( cd "$REPO_DIR" && pio run -e "$ENV" )
[ -f "$UF2" ] || err "Build finished but $UF2 not found"
info "Built $UF2"

# ── Wait for BOOTSEL ──────────────────────────────────────────────────────────
section "Put the device into BOOTSEL mode"
echo "  Hold B and tap R on the XIAO RP2040 (or hold B while plugging in)."
echo "  Waiting for the RPI-RP2 drive to mount (Ctrl-C to abort)..."

target=""
for _ in $(seq 1 120); do
    for base in "/run/media/$USER" "/media/$USER" "/media" "/mnt"; do
        [ -d "$base/RPI-RP2" ] && target="$base/RPI-RP2" && break
    done
    [ -n "$target" ] && break
    sleep 1
done
[ -n "$target" ] || err "RPI-RP2 drive never appeared. Mount it and copy $UF2 manually."
info "Found $target"

# ── Flash ─────────────────────────────────────────────────────────────────────
section "Copying firmware.uf2"
cp "$UF2" "$target/"
sync
info "Copied. The device will reboot and re-enumerate."
echo
echo "If it was already plugged in for the host install, unplug and replug it now."
