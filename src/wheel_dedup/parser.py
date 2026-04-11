import os
import re
from dataclasses import dataclass

_WHEEL_RE = re.compile(
    r"^(?P<distribution>[A-Za-z0-9]([A-Za-z0-9._]*[A-Za-z0-9])?)"
    r"-(?P<version>[A-Za-z0-9_.!+]+)"
    r"(-\d+\.?\d*)?"
    r"-(?P<python>[A-Za-z0-9.]+)"
    r"-(?P<abi>[A-Za-z0-9.]+)"
    r"-(?P<platform>[A-Za-z0-9._-]+)"
    r"\.whl$"
)


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class WheelInfo:
    filename: str
    distribution: str
    version: str

    @property
    def normalized_name(self) -> str:
        return normalize(self.distribution)


def parse_wheel(path: str) -> WheelInfo:
    basename = os.path.basename(path)
    match = _WHEEL_RE.match(basename)
    if not match:
        raise ValueError(f"Invalid wheel filename: {basename}")
    return WheelInfo(
        filename=basename,
        distribution=match.group("distribution"),
        version=match.group("version"),
    )
