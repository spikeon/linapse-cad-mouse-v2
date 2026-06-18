import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# Helper templates for spacenav_ws patching test
_OLD_TASKGROUP = """    async with asyncio.TaskGroup() as tg:
        tg.create_task(ctrl.start_mouse_event_stream(), name="mouse")
        tg.create_task(ctrl.wamp_state_handler.start_wamp_message_stream(), name="wamp")
"""

class TestInstallerMock(unittest.TestCase):
    def setUp(self):
        # Create a clean temp directory for this test run
        self.test_root = Path(tempfile.mkdtemp(prefix="linapse_inst_test_"))
        self.mock_bin = self.test_root / "bin"
        self.mock_home = self.test_root / "home"
        self.mock_bin.mkdir()
        self.mock_home.mkdir()

        # Command log file
        self.log_file = self.test_root / "commands.log"
        if self.log_file.exists():
            self.log_file.unlink()

        # Set up a dummy spacenav_ws in the mock home uv cache
        self.dummy_pkg_dir = self.mock_home / ".cache" / "uv" / "dummy_hash" / "spacenav_ws"
        self.dummy_pkg_dir.mkdir(parents=True)
        
        # Write files with content that patch-spacenav-ws.py expects
        with open(self.dummy_pkg_dir / "__init__.py", "w") as f:
            f.write("# dummy init\n")
            
        with open(self.dummy_pkg_dir / "controller.py", "w") as f:
            f.write("    def handle(self):\n        if isinstance(event, ButtonEvent):\n            pass\n")
            
        with open(self.dummy_pkg_dir / "main.py", "w") as f:
            f.write("async def main():\n" + _OLD_TASKGROUP)
            
        with open(self.dummy_pkg_dir / "spacenav.py", "w") as f:
            f.write('SPACENAV_SOCKET_PATH = "/var/run/spnav.sock"\n')

        # Write mock commands
        self.write_mock_bin("sudo", """#!/bin/bash
echo "SUDO: $*" >> {log_path}
if [[ "$*" == *"cp "* && "$*" == *"/etc/"* ]]; then
    exit 0
fi
exec "$@"
""")
        self.write_mock_bin("udevadm", """#!/bin/bash
echo "UDEVADM: $*" >> {log_path}
exit 0
""")
        self.write_mock_bin("pacman", """#!/bin/bash
echo "PACMAN: $*" >> {log_path}
if [[ "$*" == *"-Qi spacenavd"* ]]; then
    exit $MOCK_SPACENAVD_EXISTS
fi
exit 0
""")
        self.write_mock_bin("dpkg", """#!/bin/bash
echo "DPKG: $*" >> {log_path}
if [[ "$*" == *"-l spacenavd"* ]]; then
    exit $MOCK_SPACENAVD_EXISTS
fi
exit 0
""")
        self.write_mock_bin("rpm", """#!/bin/bash
echo "RPM: $*" >> {log_path}
if [[ "$*" == *"-q spacenavd"* ]]; then
    exit $MOCK_SPACENAVD_EXISTS
fi
exit 0
""")
        self.write_mock_bin("apt-get", """#!/bin/bash
echo "APT-GET: $*" >> {log_path}
exit 0
""")
        self.write_mock_bin("dnf", """#!/bin/bash
echo "DNF: $*" >> {log_path}
exit 0
""")
        self.write_mock_bin("systemctl", """#!/bin/bash
echo "SYSTEMCTL: $*" >> {log_path}
if [[ "$*" == *"is-active"* && "$*" == *"spacenavd"* ]] || [[ "$*" == *"is-enabled"* && "$*" == *"spacenavd"* ]]; then
    exit $MOCK_SPACENAVD_EXISTS
fi
exit 0
""")
        self.write_mock_bin("usermod", """#!/bin/bash
echo "USERMOD: $*" >> {log_path}
exit 0
""")
        self.write_mock_bin("pip3", """#!/bin/bash
echo "PIP3: $*" >> {log_path}
exit 0
""")
        self.write_mock_bin("uvx", """#!/bin/bash
echo "UVX: $*" >> {log_path}
exit 0
""")
        self.write_mock_bin("uv", """#!/bin/bash
echo "UV: $*" >> {log_path}
if [[ "$*" == *"spacenav_ws"* ]]; then
    echo "{dummy_pkg_dir}"
    exit 0
fi
exit 0
""", dummy_pkg_dir=self.dummy_pkg_dir)
        self.write_mock_bin("curl", """#!/bin/bash
echo "CURL: $*" >> {log_path}
exit 0
""")
        import sys
        self.write_mock_bin("python3", f"""#!/bin/bash
if [[ "$*" == *"-c import websockets"* ]]; then
    exit 0
fi
exec {sys.executable} "$@"
""")

    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.test_root, ignore_errors=True)

    def write_mock_bin(self, name, content_template, **kwargs):
        path = self.mock_bin / name
        with open(path, "w") as f:
            f.write(content_template.format(log_path=self.log_file, **kwargs))
        path.chmod(0o755)

    def run_installer_test(self, spacenavd_exists):
        # Prepare environment
        env = os.environ.copy()
        env["PATH"] = f"{self.mock_bin}:{env.get('PATH', '')}"
        env["HOME"] = str(self.mock_home)
        env["MOCK_SPACENAVD_EXISTS"] = "0" if spacenavd_exists else "1"

        # Clear command log
        if self.log_file.exists():
            self.log_file.unlink()

        # Run setup.sh
        repo_dir = Path(__file__).resolve().parents[1]
        
        # We run it with --yes to auto-accept ydotool installation prompts
        result = subprocess.run(
            ["/bin/bash", str(repo_dir / "setup.sh"), "--yes"],
            env=env,
            capture_output=True,
            text=True
        )
        
        # Verify success exit code
        self.assertEqual(result.returncode, 0, f"setup.sh failed with stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

        # Read command log
        commands = []
        if self.log_file.exists():
            with open(self.log_file) as f:
                commands = [line.strip() for line in f]

        return commands

    def test_installer_with_spacenavd_absent(self):
        commands = self.run_installer_test(spacenavd_exists=False)
        print("LOGGED COMMANDS (absent):", commands)

        # 1. Verify that spacenavd stop/disable/remove was NOT called
        stop_called = any("stop spacenavd" in c for c in commands)
        disable_called = any("disable spacenavd" in c for c in commands)
        remove_called = any("-Rns" in c and "spacenavd" in c for c in commands) or any("remove" in c and "spacenavd" in c for c in commands)

        self.assertFalse(stop_called, "Should not attempt to stop spacenavd if it is not installed")
        self.assertFalse(disable_called, "Should not attempt to disable spacenavd if it is not installed")
        self.assertFalse(remove_called, "Should not attempt to uninstall spacenavd if it is not installed")

        # 2. Verify that copy operations to /etc/udev were attempted and udevadm was called
        has_udev_copy = any("cp" in c and "99-spacemouse.rules" in c and "/etc/udev" in c for c in commands)
        has_udevadm_reload = any("udevadm" in c and "control" in c and "reload-rules" in c for c in commands)
        has_udevadm_trigger = any("udevadm" in c and "trigger" in c for c in commands)

        self.assertTrue(has_udev_copy, "Should copy 99-spacemouse.rules to /etc/udev")
        self.assertTrue(has_udevadm_reload, "Should reload udev rules")
        self.assertTrue(has_udevadm_trigger, "Should trigger udev rules")

        for cmd in commands:
            self.assertNotIn("spnavrc", cmd.lower(), "Should not access spnavrc in system directories")

        # 3. Verify user files are copied and patched
        self.verify_installation_artifacts()

    def test_installer_with_spacenavd_present(self):
        commands = self.run_installer_test(spacenavd_exists=True)

        # 1. Verify that spacenavd stop/disable/remove WAS called
        stop_called = any("stop spacenavd" in c for c in commands)
        disable_called = any("disable spacenavd" in c for c in commands)
        remove_called = any("-Rns" in c and "spacenavd" in c for c in commands) or any("remove" in c and "spacenavd" in c for c in commands)

        self.assertTrue(stop_called, "Should stop spacenavd if it is installed")
        self.assertTrue(disable_called, "Should disable spacenavd if it is installed")
        self.assertTrue(remove_called, "Should uninstall spacenavd if it is installed")

        # 2. Verify that copy operations to /etc/udev were attempted and udevadm was called
        has_udev_copy = any("cp" in c and "99-spacemouse.rules" in c and "/etc/udev" in c for c in commands)
        has_udevadm_reload = any("udevadm" in c and "control" in c and "reload-rules" in c for c in commands)
        has_udevadm_trigger = any("udevadm" in c and "trigger" in c for c in commands)

        self.assertTrue(has_udev_copy, "Should copy 99-spacemouse.rules to /etc/udev")
        self.assertTrue(has_udevadm_reload, "Should reload udev rules")
        self.assertTrue(has_udevadm_trigger, "Should trigger udev rules")

        for cmd in commands:
            self.assertNotIn("spnavrc", cmd.lower(), "Should not access spnavrc in system directories")

        # 3. Verify user files are copied and patched
        self.verify_installation_artifacts()

    def verify_installation_artifacts(self):
        # Check that files in mock home exist
        local_bin_linapse = self.mock_home / ".local" / "bin" / "linapse-service"
        self.assertTrue(local_bin_linapse.exists(), "linapse-service should be copied to user bin")
        self.assertTrue(os.access(local_bin_linapse, os.X_OK), "linapse-service should be executable")

        systemd_user_dir = self.mock_home / ".config" / "systemd" / "user"
        for svc in ["ydotoold.service", "spacenav-ws.service", "linapse-service.service", "linapse-configurator.service"]:
            self.assertTrue((systemd_user_dir / svc).exists(), f"systemd user service {svc} should exist")

        # Verify environment.d configuration
        env_conf_path = self.mock_home / ".config" / "environment.d" / "99-spnav.conf"
        self.assertTrue(env_conf_path.exists(), "environment.d config file should exist")
        with open(env_conf_path) as f:
            env_conf_content = f.read()
        self.assertEqual(env_conf_content, 'SPNAV_SOCKET="${XDG_RUNTIME_DIR}/spnav.sock"\n')

        # Verify spacenav-ws files were patched correctly
        with open(self.dummy_pkg_dir / "controller.py") as f:
            controller_content = f.read()
        self.assertIn("return", controller_content)
        self.assertNotIn("pass", controller_content)

        with open(self.dummy_pkg_dir / "main.py") as f:
            main_content = f.read()
        self.assertIn("_mouse_with_reconnect", main_content)
        self.assertNotIn("start_mouse_event_stream()", main_content.split("\n")[2]) # original shouldn't be bare

        with open(self.dummy_pkg_dir / "spacenav.py") as f:
            spacenav_content = f.read()
        self.assertIn("SPACENAV_SOCKET_PATH = f\"/run/user/{os.getuid()}/spnav.sock\"", spacenav_content)


if __name__ == "__main__":
    unittest.main()
