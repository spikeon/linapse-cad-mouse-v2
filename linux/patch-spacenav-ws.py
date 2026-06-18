#!/usr/bin/env python3
"""
Patches spacenav-ws with three fixes:

1. controller.py — buttons no longer snap the OnShape view to front
2. main.py — spacenav-ws reconnects to spacenavd automatically on replug,
             keeping the OnShape WebSocket alive (no tab refresh needed)
             and uses user-specific runtime directory socket path
3. spacenav.py — uses user-specific runtime directory socket path dynamically
                 resolved via os.getuid()

Usage:
    python3 patch-spacenav-ws.py           # auto-find and patch
    python3 patch-spacenav-ws.py /path/to/spacenav_ws/
"""
import glob
import os
import re
import subprocess
import sys


def find_package_dir():
    """Return the spacenav_ws package directory, or None."""
    # Try via uv run
    try:
        result = subprocess.run(
            [
                "uv", "run", "--with", "spacenav-ws", "python3", "-c",
                "import spacenav_ws; print(spacenav_ws.__path__[0])",
            ],
            capture_output=True, text=True, timeout=30,
        )
        path = result.stdout.strip()
        if result.returncode == 0 and path and os.path.isdir(path):
            return path
    except Exception:
        pass

    # Search uv cache
    home = os.path.expanduser("~")
    for pattern in [
        f"{home}/.cache/uv/**/spacenav_ws/__init__.py",
        f"{home}/.local/share/uv/**/spacenav_ws/__init__.py",
    ]:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return os.path.dirname(matches[0])

    return None


def patch_controller(path):
    """Disable the button-snap-to-front-view behaviour and add EOF handling."""
    with open(path) as f:
        content = f.read()

    modified = False

    # 1. Disable button-snap
    if "isinstance(event, ButtonEvent)" in content and not re.search(r"if isinstance\(event, ButtonEvent\):\s*\n\s+return\s*\n", content):
        content = re.sub(
            r"(        if isinstance\(event, ButtonEvent\):)(?:\n            [^\n]+)+",
            r"\1\n            return",
            content,
        )
        modified = True
        print(f"  controller.py: patched button-snap")

    # 2. EOF detection to trigger reconnect
    if 'if not mouse_event:' not in content:
        target = '            mouse_event = await self.reader.read(32)'
        replacement = '            mouse_event = await self.reader.read(32)\n            if not mouse_event:\n                raise ConnectionError("spacenav socket closed")'
        if target in content:
            content = content.replace(target, replacement)
            modified = True
            print(f"  controller.py: patched EOF connection handler")
        else:
            print(f"  controller.py: ERROR — read target not found", file=sys.stderr)

    if modified:
        with open(path, "w") as f:
            f.write(content)
    else:
        print(f"  controller.py: already patched")
    return True


# Reconnect wrapper inserted into nlproxy, replacing the bare TaskGroup call.
_RECONNECT_WRAPPER = """\
    async def _mouse_with_reconnect():
        while True:
            try:
                await ctrl.start_mouse_event_stream()
            except Exception as _e:
                logging.warning(f"spacenavd disconnected ({_e}), reconnecting...")
                while True:
                    await asyncio.sleep(1)
                    try:
                        from spacenav_ws.spacenav import SPACENAV_SOCKET_PATH
                        _r, _ = await asyncio.open_unix_connection(SPACENAV_SOCKET_PATH)
                        ctrl.reader = _r
                        logging.info("Reconnected to spacenavd")
                        break
                    except OSError:
                        pass

    async with asyncio.TaskGroup() as tg:
        tg.create_task(_mouse_with_reconnect(), name="mouse")
        tg.create_task(ctrl.wamp_state_handler.start_wamp_message_stream(), name="wamp")
"""

_OLD_TASKGROUP = """\
    async with asyncio.TaskGroup() as tg:
        tg.create_task(ctrl.start_mouse_event_stream(), name="mouse")
        tg.create_task(ctrl.wamp_state_handler.start_wamp_message_stream(), name="wamp")
"""


def patch_main(path):
    """Make spacenav-ws reconnect to spacenavd on replug without restarting."""
    with open(path) as f:
        content = f.read()

    if "_mouse_with_reconnect" in content and "SPACENAV_SOCKET_PATH" in content:
        print(f"  main.py: already patched with dynamic reconnect")
        return True

    if "_mouse_with_reconnect" in content:
        # Already patched with old reconnect wrapper, update the socket connection string
        target = '                        _r, _ = await asyncio.open_unix_connection("/var/run/spnav.sock")'
        replacement = '                        from spacenav_ws.spacenav import SPACENAV_SOCKET_PATH\n                        _r, _ = await asyncio.open_unix_connection(SPACENAV_SOCKET_PATH)'
        
        if target in content:
            patched = content.replace(target, replacement)
            with open(path, "w") as f:
                f.write(patched)
            print(f"  main.py: updated old patch to use dynamic SPACENAV_SOCKET_PATH")
            return True
        else:
            print(f"  main.py: ERROR — old patch target not found for replacement", file=sys.stderr)
            return False

    if _OLD_TASKGROUP not in content:
        print(f"  main.py: ERROR — patch target not found (version mismatch?)", file=sys.stderr)
        print(f"  main.py: manually replace the TaskGroup in nlproxy with a reconnect wrapper", file=sys.stderr)
        return False

    patched = content.replace(_OLD_TASKGROUP, _RECONNECT_WRAPPER)
    with open(path, "w") as f:
        f.write(patched)
    print(f"  main.py: patched")
    return True


def patch_spacenav(path):
    """Make spacenav.py use dynamic socket path based on user ID."""
    with open(path) as f:
        content = f.read()

    if 'SPACENAV_SOCKET_PATH = f"/run/user/{os.getuid()}/spnav.sock"' in content:
        print(f"  spacenav.py: already patched")
        return True

    if 'SPACENAV_SOCKET_PATH = "/var/run/spnav.sock"' not in content:
        print(f"  spacenav.py: ERROR — SPACENAV_SOCKET_PATH not found", file=sys.stderr)
        return False

    patched = content.replace(
        'SPACENAV_SOCKET_PATH = "/var/run/spnav.sock"',
        'import os\nSPACENAV_SOCKET_PATH = f"/run/user/{os.getuid()}/spnav.sock"'
    )

    with open(path, "w") as f:
        f.write(patched)
    print(f"  spacenav.py: patched")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pkg_dir = sys.argv[1]
    else:
        print("Locating spacenav-ws package...")
        pkg_dir = find_package_dir()
        if not pkg_dir:
            print(
                "ERROR: spacenav-ws not found.\n"
                "Run 'uvx spacenav-ws@latest serve --help' once to cache it, then retry.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Found: {pkg_dir}\n")

    ok = True
    ok &= patch_controller(os.path.join(pkg_dir, "controller.py"))
    ok &= patch_main(os.path.join(pkg_dir, "main.py"))
    ok &= patch_spacenav(os.path.join(pkg_dir, "spacenav.py"))
    sys.exit(0 if ok else 1)
