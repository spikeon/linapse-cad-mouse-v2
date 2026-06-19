import os
import sys
import time
import shutil
import subprocess
import asyncio
import serial
from pathlib import Path
from . import state
from .serial_port import find_serial

def find_repo_root():
    env_dir = os.environ.get("LINAPSE_REPO_DIR")
    if env_dir and Path(env_dir).joinpath("platformio.ini").exists():
        return Path(env_dir)
    try:
        p = Path(__file__).resolve()
        for parent in [p] + list(p.parents):
            if parent.joinpath("platformio.ini").exists():
                return parent
    except Exception:
        pass
    try:
        p = Path(os.getcwd()).resolve()
        for parent in [p] + list(p.parents):
            if parent.joinpath("platformio.ini").exists():
                return parent
    except Exception:
        pass
    default_dev = Path.home() / "Dev" / "linapse-cad-mouse-v2"
    if default_dev.joinpath("platformio.ini").exists():
        return default_dev
    return None

def locate_or_mount_rpi_rp2():
    if sys.platform == "darwin":
        mac_path = Path("/Volumes/RPI-RP2")
        if mac_path.exists() and mac_path.is_dir():
            return mac_path
        return None

    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            volumeNameBuffer = ctypes.create_unicode_buffer(1024)
            for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{drive_letter}:\\"
                if os.path.exists(drive):
                    if kernel32.GetVolumeInformationW(
                        ctypes.c_wchar_p(drive),
                        volumeNameBuffer,
                        ctypes.sizeof(volumeNameBuffer),
                        None, None, None, None, 0
                    ):
                        if volumeNameBuffer.value == "RPI-RP2":
                            return Path(drive)
        except Exception as e:
            print(f"[flash] Windows volume detection failed: {e}")
        return None

    import getpass
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USER", "spikeon")
    bases = [
        Path(f"/run/media/{user}/RPI-RP2"),
        Path(f"/media/{user}/RPI-RP2"),
        Path("/media/RPI-RP2"),
        Path("/mnt/RPI-RP2")
    ]
    for b in bases:
        if b.exists() and b.is_dir():
            return b
    try:
        out = subprocess.check_output(["lsblk", "-o", "PATH,LABEL"], text=True)
        for line in out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[1] == "RPI-RP2":
                device_node = parts[0]
                print(f"[flash] Found block device at {device_node}. Trying to mount via udisksctl...")
                subprocess.run(["udisksctl", "mount", "-b", device_node], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1.5)
                for b in bases:
                    if b.exists() and b.is_dir():
                        return b
    except Exception as e:
        print(f"[flash] Error searching/mounting block device: {e}")
    return None

def reset_to_bootsel(port):
    try:
        print(f"[flash] Resetting {port} to BOOTSEL mode via 1200 baud...")
        ser = serial.Serial(port, 1200)
        ser.close()
        return True
    except Exception as e:
        print(f"[flash] Failed to reset {port}: {e}")
        return False

async def flash_device():
    state.flashing_active = True
    if state.ser_holder[0]:
        try:
            print("[flash] Closing serial port...")
            state.ser_holder[0].close()
        except Exception:
            pass
        state.ser_holder[0] = None
    await state.broadcast("FLASH:status:Finding repository root...")
    repo_root = find_repo_root()
    if not repo_root:
        await state.broadcast("FLASH:error:Repository root not found. Cannot locate platformio.ini.")
        state.flashing_active = False
        return
    await state.broadcast("FLASH:status:Building firmware with PlatformIO...")
    env = os.environ.copy()
    if state.actions_ref and state.actions_ref[0]:
        custom_usb = state.actions_ref[0].get("custom_usb", {})
        if custom_usb.get("enabled", False):
            env["LINAPSE_USB_VID"] = custom_usb.get("vid", "")
            env["LINAPSE_USB_PID"] = custom_usb.get("pid", "")
            print(f"[flash] Building with custom VID={custom_usb.get('vid')}, PID={custom_usb.get('pid')}")
    pio_path = Path.home() / ".platformio" / "penv" / "bin"
    if pio_path.exists():
        env["PATH"] = str(pio_path) + os.pathsep + env.get("PATH", "")
    try:
        process = await asyncio.create_subprocess_exec(
            "pio", "run", "-e", "seeed_xiao_rp2040",
            cwd=str(repo_root),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            err_msg = stderr.decode(errors='replace')
            print(f"[flash] Build failed:\n{err_msg}")
            await state.broadcast(f"FLASH:error:Firmware compilation failed: {err_msg[:100]}...")
            state.flashing_active = False
            return
    except Exception as e:
        print(f"[flash] PlatformIO execution failed: {e}")
        await state.broadcast("FLASH:error:PlatformIO execution failed. Make sure platformio is installed.")
        state.flashing_active = False
        return
    uf2_path = repo_root / ".pio" / "build" / "seeed_xiao_rp2040" / "firmware.uf2"
    if not uf2_path.exists():
        await state.broadcast("FLASH:error:firmware.uf2 not found after build.")
        state.flashing_active = False
        return
    await state.broadcast("FLASH:status:Putting device into BOOTSEL mode...")
    port = find_serial(state.actions_ref)
    if port:
        reset_to_bootsel(port)
        await asyncio.sleep(2.0)
    else:
        print("[flash] No serial port found to reset. Device might already be in BOOTSEL or not connected.")
    await state.broadcast("FLASH:status:Waiting for RPI-RP2 drive to appear...")
    mount_point = None
    for i in range(20):
        mount_point = locate_or_mount_rpi_rp2()
        if mount_point:
            break
        await asyncio.sleep(1.0)
        await state.broadcast(f"FLASH:status:Waiting for RPI-RP2 drive... ({20 - i - 1}s remaining)")
    if not mount_point:
        await state.broadcast("FLASH:error:RPI-RP2 drive not found. Put device into BOOTSEL physically.")
        state.flashing_active = False
        return
    await state.broadcast("FLASH:status:Copying firmware to device...")
    try:
        dest_path = mount_point / "firmware.uf2"
        await asyncio.to_thread(shutil.copy, str(uf2_path), str(dest_path))
        await asyncio.to_thread(os.sync)
        await state.broadcast("FLASH:status:Firmware copied. Device rebooting...")
        await asyncio.sleep(4.0)
        await state.broadcast("FLASH:success:Flashing complete!")
    except Exception as e:
        print(f"[flash] Error copying firmware: {e}")
        await state.broadcast(f"FLASH:error:Failed to copy firmware: {e}")
    finally:
        state.flashing_active = False
