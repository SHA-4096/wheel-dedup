from unittest.mock import patch, MagicMock

from wheel_dedup.installer import install_wheel


class TestInstallWheel:
    @patch("wheel_dedup.installer.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = install_wheel("numpy-1.24.0-cp311-cp311-linux_x86_64.whl")
        assert result.success is True
        assert result.message == "OK"

    @patch("wheel_dedup.installer.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error details")
        result = install_wheel("bad-1.0.0-py3-none-any.whl")
        assert result.success is False
        assert "error details" in result.message

    @patch("wheel_dedup.installer.subprocess.run")
    def test_exception(self, mock_run):
        mock_run.side_effect = OSError("pip not found")
        result = install_wheel("pkg-1.0.0-py3-none-any.whl")
        assert result.success is False
        assert "pip not found" in result.message
