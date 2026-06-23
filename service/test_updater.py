import unittest
from unittest.mock import MagicMock, patch
import io
import json
import sys
from linapse import state
from linapse import updater

class TestUpdater(unittest.TestCase):
    def setUp(self):
        state.service_version = "2.19.1"
        state.latest_software_version = None
        state.software_update_status = "idle"
        state.software_update_url = None

    def test_compare_versions(self):
        self.assertEqual(updater.compare_versions("2.19.1", "2.19.1"), 0)
        self.assertEqual(updater.compare_versions("v2.19.1", "2.19.1"), 0)
        self.assertEqual(updater.compare_versions("v2.20.0", "v2.19.1"), 1)
        self.assertEqual(updater.compare_versions("2.19.0", "v2.19.1"), -1)
        self.assertEqual(updater.compare_versions("2.19.2", "2.19.10"), -1)
        self.assertEqual(updater.compare_versions("2.19", "2.19.1"), -1)

    @patch("urllib.request.urlopen")
    @patch("linapse.state.broadcast_from_thread")
    def test_check_for_updates_available(self, mock_broadcast, mock_urlopen):
        # Mock GitHub releases response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.20.0",
            "assets": [
                {"name": "LinapseServiceSetup.exe", "browser_download_url": "http://example.com/setup.exe"},
                {"name": "linapse-service.pkg", "browser_download_url": "http://example.com/setup.pkg"}
            ],
            "zipball_url": "http://example.com/zipball.zip",
            "html_url": "http://example.com/release"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Force platform mock if needed, or check it generic
        updater.check_for_updates(quiet=True)
        
        self.assertEqual(state.latest_software_version, "2.20.0")
        self.assertEqual(state.software_update_status, "available")
        self.assertIsNotNone(state.software_update_url)

    @patch("urllib.request.urlopen")
    @patch("linapse.state.broadcast_from_thread")
    def test_check_for_updates_up_to_date(self, mock_broadcast, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.19.1",
            "assets": []
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        updater.check_for_updates(quiet=True)
        
        self.assertEqual(state.software_update_status, "idle")
        self.assertIsNone(state.latest_software_version)
