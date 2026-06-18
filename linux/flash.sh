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

# ── VID/PID ───────────────────────────────────────────────────────────────────
section "USB VID/PID (SpaceMouse emulation)"

cur_vid="$(grep -oE 'usb_vid *= *0x[0-9A-Fa-f]+' "$INI" | grep -oE '0x[0-9A-Fa-f]+' | head -1 || true)"
cur_pid="$(grep -oE 'usb_pid *= *0x[0-9A-Fa-f]+' "$INI" | grep -oE '0x[0-9A-Fa-f]+' | head -1 || true)"

echo "  The firmware spoofs a 3Dconnexion SpaceMouse so spacenavd recognises it."
echo "  Supply the VID/PID of the model you want to emulate."
echo "  (These are intentionally not shipped in this repo — see the README security note.)"
[ -n "$cur_vid" ] && echo "  Current platformio.ini: VID=$cur_vid PID=$cur_pid"

read -rp "  VID${cur_vid:+ [$cur_vid]}: " in_vid
read -rp "  PID${cur_pid:+ [$cur_pid]}: " in_pid
VID="${in_vid:-$cur_vid}"
PID="${in_pid:-$cur_pid}"

[ -n "$VID" ] && [ -n "$PID" ] || err "VID/PID required (none supplied and none in platformio.ini)"
[[ "$VID" =~ ^0x[0-9A-Fa-f]+$ ]] || err "VID must look like 0xNNNN"
[[ "$PID" =~ ^0x[0-9A-Fa-f]+$ ]] || err "PID must look like 0xNNNN"

# Rewrite (or uncomment) the VID/PID lines in place.
sed -i -E "s|^;? *board_build.arduino.earlephilhower.usb_vid *=.*|board_build.arduino.earlephilhower.usb_vid = $VID|" "$INI"
sed -i -E "s|^;? *board_build.arduino.earlephilhower.usb_pid *=.*|board_build.arduino.earlephilhower.usb_pid = $PID|" "$INI"
info "Set VID=$VID PID=$PID in platformio.ini"

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
info "Copied. The device will reboot and re-enumerate as a SpaceMouse."
echo
echo "If it was already plugged in for the host install, unplug and replug it now."
