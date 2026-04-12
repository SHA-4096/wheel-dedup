import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from packaging.requirements import Requirement
from packaging.version import Version

from .checker import InstalledChecker
from .parser import WheelInfo, normalize


@dataclass
class Conflict:
    wheel: str
    requirement: str
    conflict_type: str
    detail: str


@dataclass
class ConflictReport:
    conflicts: List[Conflict] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0


def _extract_requires(wheel_path: str) -> List[Requirement]:
    requirements: List[Requirement] = []
    with zipfile.ZipFile(wheel_path, "r") as zf:
        metadata_files = [
            n for n in zf.namelist() if n.endswith("/METADATA") or n == "METADATA"
        ]
        if not metadata_files:
            return requirements
        with zf.open(metadata_files[0]) as f:
            for line in f:
                decoded = line.decode("utf-8").strip()
                if not decoded.startswith("Requires-Dist:"):
                    continue
                req_str = decoded[len("Requires-Dist:"):].strip()
                if ";" in req_str:
                    continue
                try:
                    requirements.append(Requirement(req_str))
                except Exception:
                    continue
    return requirements


def check_conflicts(
    to_install: List[WheelInfo],
    checker: InstalledChecker,
) -> ConflictReport:
    report = ConflictReport()

    installed = checker.get_all_installed()

    pending_versions: Dict[str, List[Version]] = {}
    pending_reqs: Dict[str, List[Requirement]] = {}

    for info in to_install:
        try:
            pending_versions.setdefault(info.normalized_name, []).append(
                Version(info.version)
            )
        except Exception:
            pass

        reqs = _extract_requires(info.path)
        pending_reqs[info.filename] = reqs

    for info in to_install:
        reqs = pending_reqs.get(info.filename, [])
        for req in reqs:
            req_name = normalize(req.name)

            if req.specifier is None or not req.specifier:
                continue

            installed_ver = installed.get(req_name)
            pending_vers = pending_versions.get(req_name)

            pending_satisfies = (
                pending_vers is not None
                and any(req.specifier.contains(pv, prereleases=True) for pv in pending_vers)
            )

            if installed_ver is not None:
                installed_satisfies = req.specifier.contains(installed_ver, prereleases=True)
                if not installed_satisfies and not pending_satisfies:
                    report.conflicts.append(
                        Conflict(
                            wheel=info.filename,
                            requirement=str(req),
                            conflict_type="installed_mismatch",
                            detail=(
                                f"{info.filename} requires {req}, "
                                f"but {req.name} {installed_ver} is installed"
                            ),
                        )
                    )
                continue

            if pending_vers is not None:
                if not pending_satisfies:
                    incompatible = [
                        pv for pv in pending_vers
                        if not req.specifier.contains(pv, prereleases=True)
                    ]
                    report.conflicts.append(
                        Conflict(
                            wheel=info.filename,
                            requirement=str(req),
                            conflict_type="inter_wheel",
                            detail=(
                                f"{info.filename} requires {req}, "
                                f"but {req.name} {incompatible[0]} is in the install list"
                            ),
                        )
                    )
            else:
                report.conflicts.append(
                    Conflict(
                        wheel=info.filename,
                        requirement=str(req),
                        conflict_type="missing",
                        detail=(
                            f"{info.filename} requires {req}, "
                            f"but {req.name} is not installed and not in wheels"
                        ),
                    )
                )

    return report
