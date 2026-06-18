#!/usr/bin/env python3
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

class TestInstallerAdversarial(unittest.TestCase):
    def setUp(self):
        # Create clean temp root
        self.test_root = Path(tempfile.mkdtemp(prefix="linapse_adv_test_", dir=Path(__file__).parent))
        self.mock_bin = self.test_root / "bin"
        self.mock_home = self.test_root / "home"
        self.mock_bin.mkdir()
        self.mock_home.mkdir()

        self.log_file = self.test_root / "commands.log"
        
        # Mock minimal environment commands so setup.sh / install.sh can run
        self.write_mock_bin("sudo", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("udevadm", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("pacman", """#!/bin/bash
exit 1
""")
        self.write_mock_bin("dpkg", """#!/bin/bash
exit 1
""")
        self.write_mock_bin("rpm", """#!/bin/bash
exit 1
""")
        self.write_mock_bin("apt-get", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("dnf", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("systemctl", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("usermod", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("pip3", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("uvx", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("uv", """#!/bin/bash
exit 0
""")
        self.write_mock_bin("curl", """#!/bin/bash
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
        shutil.rmtree(self.test_root, ignore_errors=True)

    def write_mock_bin(self, name, content_template):
        path = self.mock_bin / name
        with open(path, "w") as f:
            f.write(content_template)
        path.chmod(0o755)

    def run_installer(self, extra_env=None):
        env = os.environ.copy()
        env["PATH"] = f"{self.mock_bin}:{env.get('PATH', '')}"
        env["HOME"] = str(self.mock_home)
        if extra_env:
            env.update(extra_env)

        repo_dir = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["/bin/bash", str(repo_dir / "setup.sh"), "--yes"],
            env=env,
            capture_output=True,
            text=True
        )
        return result

    def test_xdg_runtime_dir_not_expanded_at_install_time(self):
        # Even if XDG_RUNTIME_DIR is set in the installation environment,
        # it must NOT be expanded in the generated 99-spnav.conf.
        custom_runtime_dir = "/custom/runtime/path/12345"
        result = self.run_installer(extra_env={"XDG_RUNTIME_DIR": custom_runtime_dir})
        self.assertEqual(result.returncode, 0, f"Installer failed: {result.stderr}")

        env_conf_path = self.mock_home / ".config" / "environment.d" / "99-spnav.conf"
        self.assertTrue(env_conf_path.exists())
        with open(env_conf_path) as f:
            content = f.read()

        # It must contain the literal string '${XDG_RUNTIME_DIR}'
        self.assertIn('SPNAV_SOCKET="${XDG_RUNTIME_DIR}/spnav.sock"', content)
        # It must NOT contain the expanded custom path
        self.assertNotIn(custom_runtime_dir, content)

    @unittest.skipIf(os.geteuid() == 0, "Cannot run write-prevention tests as root")
    def test_install_fails_when_directory_is_unwritable(self):
        # Create directory and make it read-only
        env_d_dir = self.mock_home / ".config" / "environment.d"
        env_d_dir.mkdir(parents=True)
        env_d_dir.chmod(0o400) # Read-only, no write or execute for owner

        try:
            result = self.run_installer()
            # The installer should fail because it cannot write to ~/.config/environment.d/99-spnav.conf
            self.assertNotEqual(result.returncode, 0)
        finally:
            # Restore permissions so tearDown can clean up
            env_d_dir.chmod(0o755)

    @unittest.skipIf(os.geteuid() == 0, "Cannot run write-prevention tests as root")
    def test_install_fails_when_file_is_readonly(self):
        # Create file and make it read-only
        env_d_dir = self.mock_home / ".config" / "environment.d"
        env_d_dir.mkdir(parents=True)
        conf_file = env_d_dir / "99-spnav.conf"
        conf_file.touch()
        conf_file.chmod(0o400) # Read-only

        try:
            result = self.run_installer()
            # The installer should fail because it cannot overwrite ~/.config/environment.d/99-spnav.conf
            self.assertNotEqual(result.returncode, 0)
        finally:
            # Restore permissions
            conf_file.chmod(0o644)

    def test_install_handles_symlink_correctly(self):
        # Create target and make 99-spnav.conf a symlink to it
        env_d_dir = self.mock_home / ".config" / "environment.d"
        env_d_dir.mkdir(parents=True)
        
        target_file = self.test_root / "my_custom_target"
        target_file.touch()
        
        conf_file = env_d_dir / "99-spnav.conf"
        conf_file.symlink_to(target_file)

        result = self.run_installer()
        self.assertEqual(result.returncode, 0)
        
        # Verify that target_file was written to, following the symlink
        with open(target_file) as f:
            content = f.read()
        self.assertIn('SPNAV_SOCKET="${XDG_RUNTIME_DIR}/spnav.sock"', content)

if __name__ == "__main__":
    unittest.main()
