from unittest.mock import patch, MagicMock

from wheel_dedup.checker import InstalledChecker


def _make_dist(name: str, version: str) -> MagicMock:
    dist = MagicMock()
    dist.metadata = {"Name": name, "Version": version}
    return dist


class TestInstalledChecker:
    @patch("wheel_dedup.checker.importlib.metadata.distributions")
    def test_installed_package(self, mock_dists):
        mock_dists.return_value = [
            _make_dist("numpy", "1.24.0"),
            _make_dist("requests", "2.28.0"),
        ]
        checker = InstalledChecker()
        assert checker.is_installed("numpy") is True
        assert checker.get_installed_version("numpy") == "1.24.0"

    @patch("wheel_dedup.checker.importlib.metadata.distributions")
    def test_not_installed(self, mock_dists):
        mock_dists.return_value = [_make_dist("numpy", "1.24.0")]
        checker = InstalledChecker()
        assert checker.is_installed("flask") is False
        assert checker.get_installed_version("flask") is None

    @patch("wheel_dedup.checker.importlib.metadata.distributions")
    def test_normalized_lookup(self, mock_dists):
        mock_dists.return_value = [_make_dist("My_Package", "3.0.0")]
        checker = InstalledChecker()
        assert checker.is_installed("my-package") is True
        assert checker.get_installed_version("my-package") == "3.0.0"
        assert checker.is_installed("My_Package") is True

    @patch("wheel_dedup.checker.importlib.metadata.distributions")
    def test_cache_loaded_once(self, mock_dists):
        mock_dists.return_value = [_make_dist("numpy", "1.24.0")]
        checker = InstalledChecker()
        checker.is_installed("numpy")
        checker.is_installed("flask")
        assert mock_dists.call_count == 1
