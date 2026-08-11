"""
Lanvan Docker Network & Address Resolution Regression Test Suite
Verifies single source of truth address resolution, Docker bridge IP rejection, and LANVAN_ADVERTISE_HOST overrides.
"""
import os
import sys
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.utils.network_resolver import is_docker_bridge_ip, resolve_advertise_host

class TestDockerNetworkResolution(unittest.TestCase):

    def setUp(self):
        self.original_env = os.environ.get("LANVAN_ADVERTISE_HOST")
        if "LANVAN_ADVERTISE_HOST" in os.environ:
            del os.environ["LANVAN_ADVERTISE_HOST"]

    def tearDown(self):
        if self.original_env:
            os.environ["LANVAN_ADVERTISE_HOST"] = self.original_env
        elif "LANVAN_ADVERTISE_HOST" in os.environ:
            del os.environ["LANVAN_ADVERTISE_HOST"]

    def test_docker_bridge_ip_rejection(self):
        # Temporarily mock docker environment flag
        import app.utils.network_resolver as nr
        original_fn = nr.is_docker_environment
        nr.is_docker_environment = lambda: True

        try:
            self.assertTrue(is_docker_bridge_ip("172.17.0.2"))
            self.assertTrue(is_docker_bridge_ip("172.18.0.5"))
            self.assertTrue(is_docker_bridge_ip("172.31.255.254"))
            self.assertTrue(is_docker_bridge_ip("127.0.0.1"))

            self.assertFalse(is_docker_bridge_ip("192.168.1.34"))
            self.assertFalse(is_docker_bridge_ip("10.0.0.15"))
        finally:
            nr.is_docker_environment = original_fn

    def test_lanvan_advertise_host_override(self):
        os.environ["LANVAN_ADVERTISE_HOST"] = "192.168.1.34"
        res = resolve_advertise_host()
        self.assertEqual(res["lan_ip"], "192.168.1.34")
        self.assertEqual(res["display_ip"], "192.168.1.34")
        self.assertTrue(res["is_override"])

    def test_docker_bridge_fallback(self):
        import app.utils.network_resolver as nr
        original_fn = nr.is_docker_environment
        nr.is_docker_environment = lambda: True

        try:
            res = resolve_advertise_host()
            self.assertIsNone(res["lan_ip"])
            self.assertEqual(res["display_ip"], "127.0.0.1")
            self.assertTrue(res["is_docker"])
            self.assertFalse(res["is_override"])
        finally:
            nr.is_docker_environment = original_fn

    def test_non_docker_address_validity(self):
        import app.utils.network_resolver as nr
        original_fn = nr.is_docker_environment
        nr.is_docker_environment = lambda: False

        try:
            res = resolve_advertise_host()
            self.assertFalse(res["is_docker"])
            if res["lan_ip"]:
                self.assertFalse(res["lan_ip"].startswith("172.17."))
                self.assertFalse(res["lan_ip"].startswith("127."))
        finally:
            nr.is_docker_environment = original_fn

if __name__ == "__main__":
    unittest.main()
