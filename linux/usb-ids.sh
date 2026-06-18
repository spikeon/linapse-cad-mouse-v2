#!/bin/bash
# Shared resolver for the spoofed SpaceMouse USB VID/PID.
# Source this (don't execute it) — it sets shell variables for the caller.
#
# Resolution order:  environment  →  value already in platformio.ini.
# There is no built-in default: the spoofed SpaceMouse VID/PID are NOT shipped
# in this repo (see the README security note). Supply your own:
#   LINAPSE_USB_VID=0xXXXX LINAPSE_USB_PID=0xYYYY ./setup.sh
# or fill them into platformio.ini before running.
#
# Sets:
#   LINAPSE_USB_VID / LINAPSE_USB_PID            — 0xNNNN form (platformio build flags)
#   LINAPSE_USB_VID_UDEV / LINAPSE_USB_PID_UDEV  — lowercase 4-digit hex, no 0x (udev rules)

_usbids_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_usbids_ini="$_usbids_repo/platformio.ini"

_usbids_ini_vid="$(grep -oE 'usb_vid *= *0x[0-9A-Fa-f]+' "$_usbids_ini" 2>/dev/null | grep -oE '0x[0-9A-Fa-f]+' | head -1)"
_usbids_ini_pid="$(grep -oE 'usb_pid *= *0x[0-9A-Fa-f]+' "$_usbids_ini" 2>/dev/null | grep -oE '0x[0-9A-Fa-f]+' | head -1)"

LINAPSE_USB_VID="${LINAPSE_USB_VID:-$_usbids_ini_vid}"
LINAPSE_USB_PID="${LINAPSE_USB_PID:-$_usbids_ini_pid}"

[ -n "$LINAPSE_USB_VID" ] && [ -n "$LINAPSE_USB_PID" ] || {
    echo "ERROR: USB VID/PID not set. Export LINAPSE_USB_VID / LINAPSE_USB_PID (e.g. 0xNNNN)" >&2
    echo "       or fill them into platformio.ini. They are intentionally not shipped." >&2
    exit 1
}
[[ "$LINAPSE_USB_VID" =~ ^0x[0-9A-Fa-f]{1,4}$ ]] || { echo "ERROR: LINAPSE_USB_VID must look like 0xNNNN (got '$LINAPSE_USB_VID')" >&2; exit 1; }
[[ "$LINAPSE_USB_PID" =~ ^0x[0-9A-Fa-f]{1,4}$ ]] || { echo "ERROR: LINAPSE_USB_PID must look like 0xNNNN (got '$LINAPSE_USB_PID')" >&2; exit 1; }

# udev matches lowercase 4-digit hex without the 0x prefix.
LINAPSE_USB_VID_UDEV="$(printf '%04x' "$LINAPSE_USB_VID")"
LINAPSE_USB_PID_UDEV="$(printf '%04x' "$LINAPSE_USB_PID")"
