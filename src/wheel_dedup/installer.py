import subprocess
import sys
from dataclasses import dataclass


@dataclass
class InstallResult:
    wheel: str
    success: bool
    message: str


def install_wheel(wheel_path: str, *, verbose: bool = False) -> InstallResult:
    cmd = [sys.executable, "-m", "pip", "install", wheel_path]
    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
        )
        if result.returncode == 0:
            return InstallResult(wheel=wheel_path, success=True, message="OK")
        else:
            err = result.stderr.strip() if result.stderr else "unknown error"
            return InstallResult(wheel=wheel_path, success=False, message=err)
    except Exception as e:
        return InstallResult(wheel=wheel_path, success=False, message=str(e))
