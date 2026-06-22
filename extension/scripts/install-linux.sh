#!/usr/bin/env bash
# Install the Linapse Browser Connector via managed browser policies when possible.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
META="$EXT_DIR/extension-id.json"

err() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }
section() { echo; echo "==> $*"; }

command -v python3 >/dev/null || err "python3 is required"

read_meta() {
  python3 - "$1" "$META" <<'PY'
import json, sys
print(json.load(open(sys.argv[2]))[sys.argv[1]])
PY
}

CHROME_ID="$(read_meta chrome_extension_id)"
FIREFOX_ID="$(read_meta firefox_extension_id)"
CHROME_URL="$(read_meta chrome_web_store_url)"
EDGE_URL="$(read_meta edge_addons_url)"
FIREFOX_URL="$(read_meta firefox_addons_url)"

FORCE_INSTALL_VALUE=""
EDGE_FORCE_INSTALL_VALUE=""
if [ -n "$CHROME_ID" ]; then
  FORCE_INSTALL_VALUE="${CHROME_ID};https://clients2.google.com/service/update2/crx"
  EDGE_FORCE_INSTALL_VALUE="${CHROME_ID};https://edge.microsoft.com/extensionwebstorebase/v1/crx"
fi

install_chrome_policy() {
  local policy_dir="$1"
  mkdir -p "$policy_dir"
  cat > "$policy_dir/linapse-browser-connector.json" <<EOF
{
  "ExtensionInstallForcelist": [
    "${FORCE_INSTALL_VALUE}"
  ]
}
EOF
  info "Wrote Chrome policy: $policy_dir/linapse-browser-connector.json"
}

install_edge_policy() {
  local policy_dir="$1"
  mkdir -p "$policy_dir"
  cat > "$policy_dir/linapse-browser-connector.json" <<EOF
{
  "ExtensionInstallForcelist": [
    "${EDGE_FORCE_INSTALL_VALUE}"
  ]
}
EOF
  info "Wrote Edge policy: $policy_dir/linapse-browser-connector.json"
}

install_firefox_policy() {
  local policy_dir="$1"
  mkdir -p "$policy_dir"
  cat > "$policy_dir/policies.json" <<EOF
{
  "policies": {
    "Extensions": {
      "Install": [
        "https://addons.mozilla.org/firefox/downloads/latest/linapse-browser-connector/latest.xpi"
      ]
    }
  }
}
EOF
  info "Wrote Firefox policy: $policy_dir/policies.json"
}

open_store_pages() {
  info "Opening official store pages for manual install..."
  for url in "$CHROME_URL" "$EDGE_URL" "$FIREFOX_URL"; do
    if command -v xdg-open >/dev/null; then
      xdg-open "$url" >/dev/null 2>&1 || true
    elif command -v open >/dev/null; then
      open "$url" >/dev/null 2>&1 || true
    else
      info "Install manually: $url"
    fi
  done
}

print_store_links() {
  info "Install the extension from your browser's store (links below)."
  info "To open all store pages automatically: LINAPSE_OPEN_STORE_PAGES=1 $0"
}

section "Linapse Browser Connector"

POLICY_INSTALLED=0
if [ -z "$CHROME_ID" ]; then
  info "chrome_extension_id is not set in extension-id.json — skipping managed policy install."
  info "After Chrome Web Store publish, add the Item ID to extension-id.json for force-install."
elif [ "${EUID:-$(id -u)}" -eq 0 ] || [ "${LINAPSE_INSTALL_BROWSER_POLICY:-0}" = "1" ]; then
  section "Installing managed browser policies (requires sudo for system-wide install)"
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    sudo "$0" "$@" || info "Policy install skipped (declined or failed)."
  else
    install_chrome_policy /etc/opt/chrome/policies/managed
    install_chrome_policy /etc/chromium/policies/managed
    install_edge_policy /etc/opt/edge/policies/managed
    install_firefox_policy /etc/firefox/policies
    install_firefox_policy /usr/lib/firefox/distribution
    POLICY_INSTALLED=1
    info "Restart Chrome, Edge, and Firefox to apply policies."
  fi
else
  info "Skipping system policy install."
  info "Re-run with sudo or LINAPSE_INSTALL_BROWSER_POLICY=1 to force-install from the official stores."
fi

if [ "$POLICY_INSTALLED" -eq 0 ]; then
  if [ "${LINAPSE_OPEN_STORE_PAGES:-0}" = "1" ]; then
    open_store_pages
  else
    print_store_links
  fi
fi

section "Browser connector setup"
cat <<EOF

Install the official Linapse Browser Connector from your browser's extension store:
  Chrome:  $CHROME_URL
  Edge:    $EDGE_URL
  Firefox: $FIREFOX_URL

Safari users: see docs/BROWSER_EXTENSION.md for the Safari Web Extension build.

Then open https://cad.onshape.com or SketchUp Web and move the CAD Mouse.
EOF
