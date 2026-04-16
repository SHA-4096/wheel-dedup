import os
import zipfile
from typing import Dict, List

from wheel_dedup.checker import InstalledChecker
from wheel_dedup.conflict import Conflict, ConflictReport, check_conflicts, _extract_requires
from wheel_dedup.parser import WheelInfo, normalize, parse_wheel


def _build_wheel(
    path: str, name: str, version: str, requires: List[str] = None
) -> str:
    dist_info = f"{name}-{version}.dist-info"
    lines = [f"Name: {name}", f"Version: {version}"]
    if requires:
        lines.append("")
        for r in requires:
            lines.append(f"Requires-Dist: {r}")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{dist_info}/METADATA", "\n".join(lines).encode())
    return path


def _build_info(tmp_path, name, version, requires=None):
    filename = f"{name}-{version}-py3-none-any.whl"
    path = _build_wheel(str(tmp_path / filename), name, version, requires)
    return parse_wheel(path)


def _checker(installed: Dict[str, str]) -> InstalledChecker:
    c = InstalledChecker()
    c._cache = dict(installed)
    c._loaded = True
    return c


class TestExtractRequiresFromRealWheel:
    def test_reads_requires_dist(self, tmp_path):
        _build_wheel(
            str(tmp_path / "pkg-1.0.0-py3-none-any.whl"),
            "pkg", "1.0.0",
            requires=["foo>=1.0", "bar"],
        )
        reqs = _extract_requires(str(tmp_path / "pkg-1.0.0-py3-none-any.whl"))
        names = [r.name for r in reqs]
        assert "foo" in names
        assert "bar" in names

    def test_ignores_conditional(self, tmp_path):
        _build_wheel(
            str(tmp_path / "pkg-1.0.0-py3-none-any.whl"),
            "pkg", "1.0.0",
            requires=['winapi ; sys_platform=="win32"', "foo>=1.0"],
        )
        reqs = _extract_requires(str(tmp_path / "pkg-1.0.0-py3-none-any.whl"))
        names = [r.name for r in reqs]
        assert "winapi" not in names
        assert "foo" in names

    def test_no_metadata_returns_empty(self, tmp_path):
        path = str(tmp_path / "empty-1.0.0-py3-none-any.whl")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("empty-1.0.0.dist-info/RECORD", "")
        reqs = _extract_requires(path)
        assert reqs == []


class TestEndToEndNoConflict:
    def test_all_installed_skip(self, tmp_path):
        info = _build_info(tmp_path, "numpy", "1.24.0")
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_new_wheel_no_deps(self, tmp_path):
        info = _build_info(tmp_path, "fresh_pkg", "1.0.0")
        checker = _checker({})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_dep_satisfied_by_installed(self, tmp_path):
        info = _build_info(tmp_path, "app", "2.0.0", requires=["numpy>=1.20"])
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_dep_satisfied_by_pending_wheel(self, tmp_path):
        info_app = _build_info(tmp_path, "app", "1.0.0", requires=["dep>=2.0"])
        info_dep = _build_info(tmp_path, "dep", "2.5.0")
        checker = _checker({})
        report = check_conflicts([info_app, info_dep], checker)
        assert not report.has_conflicts

    def test_installed_mismatch_resolved_by_pending(self, tmp_path):
        info_app = _build_info(tmp_path, "app", "1.0.0", requires=["dep>=2.0"])
        info_dep = _build_info(tmp_path, "dep", "3.0.0")
        checker = _checker({"dep": "1.0.0"})
        report = check_conflicts([info_app, info_dep], checker)
        assert not report.has_conflicts


class TestEndToEndInstalledMismatch:
    def test_installed_too_old(self, tmp_path):
        info = _build_info(tmp_path, "app", "1.0.0", requires=["numpy>=2.0"])
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        c = report.conflicts[0]
        assert c.conflict_type == "installed_mismatch"
        assert "numpy" in c.detail
        assert "1.24.0" in c.detail

    def test_installed_too_new(self, tmp_path):
        info = _build_info(tmp_path, "app", "1.0.0", requires=["numpy<2.0"])
        checker = _checker({"numpy": "2.4.4"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "installed_mismatch"

    def test_multiple_mismatches(self, tmp_path):
        info = _build_info(
            tmp_path, "app", "1.0.0", requires=["numpy>=2.0", "pandas>=4.0"]
        )
        checker = _checker({"numpy": "1.0.0", "pandas": "3.0.0"})
        report = check_conflicts([info], checker)
        assert len(report.conflicts) == 2
        types = {c.conflict_type for c in report.conflicts}
        assert types == {"installed_mismatch"}


class TestEndToEndInterWheelConflict:
    def test_pending_version_incompatible(self, tmp_path):
        info_app = _build_info(tmp_path, "app", "1.0.0", requires=["dep>=2.0"])
        info_dep = _build_info(tmp_path, "dep", "1.0.0")
        checker = _checker({})
        report = check_conflicts([info_app, info_dep], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "inter_wheel"

    def test_compatible_version_among_multiple_pending(self, tmp_path):
        info_app = _build_info(tmp_path, "app", "1.0.0", requires=["dep>=2.0"])
        info_dep_old = _build_info(tmp_path, "dep", "1.0.0")
        info_dep_new = _build_info(tmp_path, "dep", "3.0.0")
        checker = _checker({})
        report = check_conflicts([info_app, info_dep_old, info_dep_new], checker)
        assert not report.has_conflicts

    def test_cross_deps_between_wheels(self, tmp_path):
        info_a = _build_info(tmp_path, "pkg_a", "1.0.0", requires=["pkg-b>=2.0"])
        info_b = _build_info(tmp_path, "pkg_b", "1.0.0", requires=["pkg-a>=2.0"])
        checker = _checker({})
        report = check_conflicts([info_a, info_b], checker)
        assert report.has_conflicts
        types = {c.conflict_type for c in report.conflicts}
        assert types == {"inter_wheel"}


class TestEndToEndMissingDependency:
    def test_simple_missing(self, tmp_path):
        info = _build_info(tmp_path, "app", "1.0.0", requires=["nonexistent>=1.0"])
        checker = _checker({})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "missing"
        assert "nonexistent" in report.conflicts[0].detail

    def test_missing_when_installed_version_mismatch_and_no_pending(self, tmp_path):
        info = _build_info(tmp_path, "app", "1.0.0", requires=["numpy>=99.0"])
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "installed_mismatch"

    def test_dep_present_as_pending_avoids_missing(self, tmp_path):
        info_app = _build_info(tmp_path, "app", "1.0.0", requires=["dep>=1.0"])
        info_dep = _build_info(tmp_path, "dep", "2.0.0")
        checker = _checker({})
        report = check_conflicts([info_app, info_dep], checker)
        assert not report.has_conflicts


class TestEndToEndNormalizedNames:
    def test_underscore_vs_hyphen(self, tmp_path):
        info = _build_info(tmp_path, "my_pkg", "1.0.0", requires=["my-dep>=2.0"])
        info_dep = _build_info(tmp_path, "my_dep", "2.5.0")
        checker = _checker({"my-dep": "2.5.0"})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_case_insensitive_conflict(self, tmp_path):
        info = _build_info(tmp_path, "app", "1.0.0", requires=["NumPy>=99.0"])
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "installed_mismatch"


class TestEndToEndConditionalDeps:
    def test_win32_conditional_ignored(self, tmp_path):
        info = _build_info(
            tmp_path, "app", "1.0.0",
            requires=['pywin32>=200 ; sys_platform=="win32"'],
        )
        checker = _checker({})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_mixed_conditional_and_unconditional(self, tmp_path):
        info = _build_info(
            tmp_path, "app", "1.0.0",
            requires=[
                'pywin32>=200 ; sys_platform=="win32"',
                "numpy>=99.0",
            ],
        )
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert len(report.conflicts) == 1
        assert "numpy" in report.conflicts[0].detail


class TestEndToEndMixedScenario:
    def test_skip_install_conflict(self, tmp_path):
        info_skip = _build_info(tmp_path, "numpy", "1.24.0")
        info_install = _build_info(tmp_path, "app", "1.0.0", requires=["numpy>=2.0"])
        checker = _checker({"numpy": "1.24.0"})
        report = check_conflicts([info_install], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "installed_mismatch"

    def test_multiple_wheels_multiple_conflict_types(self, tmp_path):
        info_a = _build_info(tmp_path, "pkg_a", "1.0.0", requires=["old-lib>=2.0"])
        info_b = _build_info(tmp_path, "old_lib", "1.0.0")
        info_c = _build_info(tmp_path, "pkg_c", "1.0.0", requires=["ghost>=1.0"])
        checker = _checker({})
        report = check_conflicts([info_a, info_b, info_c], checker)
        assert report.has_conflicts
        types = {c.conflict_type for c in report.conflicts}
        assert "inter_wheel" in types
        assert "missing" in types
