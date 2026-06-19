import unittest
import yaml
from pathlib import Path
import configparser

class TestInstallerConfig(unittest.TestCase):
    def setUp(self):
        self.repo_dir = Path(__file__).resolve().parents[1]
        self.workflow_path = self.repo_dir / ".github" / "workflows" / "multi-distro-test.yml"
        self.installer_path = self.repo_dir / "installer.iss"

    def test_workflow_yaml_valid(self):
        self.assertTrue(self.workflow_path.exists(), "Workflow file does not exist")
        with open(self.workflow_path, "r") as f:
            try:
                data = yaml.safe_load(f)
            except Exception as e:
                self.fail(f"Workflow file is not valid YAML: {e}")

        # Check jobs
        jobs = data.get("jobs", {})
        self.assertIn("build-windows", jobs, "build-windows job not found in workflow")
        self.assertIn("build-macos", jobs, "build-macos job not found in workflow")

        # Validate build-windows steps
        win_job = jobs["build-windows"]
        self.assertEqual(win_job.get("runs-on"), "windows-latest")
        win_steps = win_job.get("steps", [])
        step_names = [step.get("name", "") for step in win_steps]
        self.assertTrue(any("Checkout" in name for name in step_names), "Checkout step missing in build-windows")
        self.assertTrue(any("Python" in name for name in step_names), "Setup Python step missing in build-windows")
        self.assertTrue(any("Install" in name for name in step_names), "Install dependencies step missing in build-windows")
        self.assertTrue(any("Compile" in name for name in step_names), "Compile step missing in build-windows")
        self.assertTrue(any("Update" in name for name in step_names), "Update AppVersion step missing in build-windows")
        self.assertTrue(any("iscc" in step.get("run", "") for step in win_steps), "ISCC compile step missing in build-windows")
        self.assertTrue(any("upload-artifact" in step.get("uses", "") for step in win_steps), "Upload artifact step missing in build-windows")

        # Validate build-macos steps
        mac_job = jobs["build-macos"]
        self.assertEqual(mac_job.get("runs-on"), "macos-latest")
        mac_steps = mac_job.get("steps", [])
        mac_step_names = [step.get("name", "") for step in mac_steps]
        self.assertTrue(any("Checkout" in name for name in mac_step_names), "Checkout step missing in build-macos")
        self.assertTrue(any("Python" in name for name in mac_step_names), "Setup Python step missing in build-macos")
        self.assertTrue(any("Install" in name for name in mac_step_names), "Install dependencies step missing in build-macos")
        self.assertTrue(any("Compile" in name for name in mac_step_names), "Compile step missing in build-macos")
        self.assertTrue(any("Prepare launchd" in name for name in mac_step_names), "Prepare launchd step missing in build-macos")
        self.assertTrue(any("pkgbuild" in step.get("run", "") for step in mac_steps), "pkgbuild step missing in build-macos")
        self.assertTrue(any("upload-artifact" in step.get("uses", "") for step in mac_steps), "Upload artifact step missing in build-macos")

    def test_installer_iss_valid(self):
        self.assertTrue(self.installer_path.exists(), "installer.iss does not exist")
        
        # Read the file content
        with open(self.installer_path, "r") as f:
            content = f.read()

        # Simple verification of section presence
        self.assertIn("[Setup]", content)
        self.assertIn("[Files]", content)
        self.assertIn("[Run]", content)

        # Parse sections manually or with configparser
        # Note: Inno Setup keys might not have spaces around '=' and configparser can parse them
        parser = configparser.ConfigParser(strict=False, interpolation=None)
        # configparser requires section headers, so we can parse it
        try:
            parser.read_string(content)
        except Exception as e:
            self.fail(f"Failed to parse installer.iss as INI: {e}")

        # Check [Setup] settings
        setup = dict(parser.items("Setup"))
        self.assertEqual(setup.get("appname"), "Linapse CAD Mouse Service")
        self.assertEqual(setup.get("appversion"), "2.5.2")
        self.assertEqual(setup.get("defaultdirname"), "{autopf}\\LinapseCADMouse")
        self.assertEqual(setup.get("defaultgroupname"), "Linapse CAD Mouse")
        self.assertEqual(setup.get("outputdir"), ".")
        self.assertEqual(setup.get("outputbasefilename"), "LinapseServiceSetup")
        self.assertEqual(setup.get("compression"), "lzma")
        self.assertEqual(setup.get("solidcompression"), "yes")

        # Check [Files] settings
        files_content = content.split("[Files]")[1].split("[")[0].strip()
        self.assertIn('Source: "dist\\linapse-service.exe"', files_content)
        self.assertIn('DestDir: "{app}"', files_content)

        # Check [Run] settings
        run_content = content.split("[Run]")[1].split("[")[0].strip()
        self.assertIn('Filename: "{app}\\linapse-service.exe"', run_content)

if __name__ == "__main__":
    unittest.main()
