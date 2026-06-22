#!/usr/bin/env python3
"""Sync version from VERSION file to all files that embed the version string.

Run from any directory. Only rewrites files that are out of date.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION = ROOT.joinpath("VERSION").read_text().strip()

if not VERSION:
    print("ERROR: VERSION file is empty", file=sys.stderr)
    sys.exit(1)


def patch(path, pattern, replacement):
    text = path.read_text()
    new_text = re.sub(pattern, replacement, text)
    if new_text == text:
        print(f"  {path.relative_to(ROOT)}: already {VERSION}")
    else:
        path.write_text(new_text)
        print(f"  {path.relative_to(ROOT)}: -> {VERSION}")


print(f"sync_version: {VERSION}")

# firmware/src/main.cpp: Serial.println("version=X.Y.Z")
patch(
    ROOT / "firmware/src/main.cpp",
    r'(Serial\.println\("version=)[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# service/linapse/state.py: service_version = "X.Y.Z"
patch(
    ROOT / "service/linapse/state.py",
    r'(service_version\s*=\s*")[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# installer.iss: AppVersion=X.Y.Z
patch(
    ROOT / "installer.iss",
    r'(?m)^(AppVersion=).*',
    rf'\g<1>{VERSION}',
)

# configurator/package.json: "version": "X.Y.Z"
patch(
    ROOT / "configurator/package.json",
    r'("version"\s*:\s*")[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# service/linapse-browser-connector.user.js: // @version      X.Y.Z
patch(
    ROOT / "service/linapse-browser-connector.user.js",
    r'(// @version\s+)\S+',
    rf'\g<1>{VERSION}',
)

print("done")
