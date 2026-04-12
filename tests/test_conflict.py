import os
import zipfile
from unittest.mock import patch

from wheel_dedup.checker import InstalledChecker
from wheel_dedup.conflict import check_conflicts, ConflictReport
from wheel_dedup.parser import WheelInfo


def _make_wheel(path: str, name: str, version: str, requires: list = None) -> str:
    basename = os.path.basename(path)
    dist_info = f"{name}-{version}.dist-info"
    metadata_lines = [
        f"Name: {name}",
        f"Version: {version}",
    ]
    if requires:
        metadata_lines.append("")
        for req in requires:
            metadata_lines.append(f"Requires-Dist: {req}")

    metadata_content = "\n".join(metadata_lines).encode("utf-8")

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{dist_info}/METADATA", metadata_content)

    return path


def _make_checker(installed: dict) -> InstalledChecker:
    checker = InstalledChecker()
    checker._cache = dict(installed)
    checker._loaded = True
    return checker


class TestNoConflicts:
    def test_no_requirements(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"), "foo", "1.0.0"
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_satisfied_by_installed(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({"bar": "2.5.0"})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts

    def test_satisfied_by_pending_wheel(self, tmp_path):
        whl_a = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        whl_b = _make_wheel(
            str(tmp_path / "bar-2.5.0-py3-none-any.whl"),
            "bar",
            "2.5.0",
        )
        info_a = WheelInfo(path=whl_a, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        info_b = WheelInfo(path=whl_b, filename="bar-2.5.0-py3-none-any.whl", distribution="bar", version="2.5.0")
        checker = _make_checker({})
        report = check_conflicts([info_a, info_b], checker)
        assert not report.has_conflicts


class TestInstalledMismatch:
    def test_installed_version_too_old(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({"bar": "1.5.0"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "installed_mismatch"
        assert "bar" in report.conflicts[0].detail
        assert "1.5.0" in report.conflicts[0].detail


class TestInterWheelConflict:
    def test_pending_wheel_version_incompatible(self, tmp_path):
        whl_a = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        whl_b = _make_wheel(
            str(tmp_path / "bar-1.0.0-py3-none-any.whl"),
            "bar",
            "1.0.0",
        )
        info_a = WheelInfo(path=whl_a, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        info_b = WheelInfo(path=whl_b, filename="bar-1.0.0-py3-none-any.whl", distribution="bar", version="1.0.0")
        checker = _make_checker({})
        report = check_conflicts([info_a, info_b], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "inter_wheel"


class TestMissingDependency:
    def test_dependency_not_installed_not_in_wheels(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "missing"


class TestConditionalDeps:
    def test_conditional_deps_ignored(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=['bar>=2.0 ; sys_platform=="win32"'],
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts


class TestNoSpecifier:
    def test_no_version_specifier_is_ok(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar"],
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({"bar": "1.0.0"})
        report = check_conflicts([info], checker)
        assert not report.has_conflicts


class TestInstalledMismatchResolvedByPending:
    def test_mismatch_resolved_by_pending_wheel(self, tmp_path):
        whl_foo = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        whl_bar = _make_wheel(
            str(tmp_path / "bar-3.0.0-py3-none-any.whl"),
            "bar",
            "3.0.0",
        )
        info_foo = WheelInfo(path=whl_foo, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        info_bar = WheelInfo(path=whl_bar, filename="bar-3.0.0-py3-none-any.whl", distribution="bar", version="3.0.0")
        checker = _make_checker({"bar": "1.0.0"})
        report = check_conflicts([info_foo, info_bar], checker)
        assert not report.has_conflicts

    def test_mismatch_not_resolved_when_no_pending(self, tmp_path):
        whl = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        info = WheelInfo(path=whl, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        checker = _make_checker({"bar": "1.0.0"})
        report = check_conflicts([info], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "installed_mismatch"


class TestInterWheelMultipleVersions:
    def test_compatible_pending_version_exists(self, tmp_path):
        whl_foo = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        whl_bar_old = _make_wheel(
            str(tmp_path / "bar-1.0.0-py3-none-any.whl"),
            "bar",
            "1.0.0",
        )
        whl_bar_new = _make_wheel(
            str(tmp_path / "bar-3.0.0-py3-none-any.whl"),
            "bar",
            "3.0.0",
        )
        info_foo = WheelInfo(path=whl_foo, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        info_bar_old = WheelInfo(path=whl_bar_old, filename="bar-1.0.0-py3-none-any.whl", distribution="bar", version="1.0.0")
        info_bar_new = WheelInfo(path=whl_bar_new, filename="bar-3.0.0-py3-none-any.whl", distribution="bar", version="3.0.0")
        checker = _make_checker({})
        report = check_conflicts([info_foo, info_bar_old, info_bar_new], checker)
        assert not report.has_conflicts

    def test_no_compatible_pending_version(self, tmp_path):
        whl_foo = _make_wheel(
            str(tmp_path / "foo-1.0.0-py3-none-any.whl"),
            "foo",
            "1.0.0",
            requires=["bar>=2.0"],
        )
        whl_bar = _make_wheel(
            str(tmp_path / "bar-1.0.0-py3-none-any.whl"),
            "bar",
            "1.0.0",
        )
        info_foo = WheelInfo(path=whl_foo, filename="foo-1.0.0-py3-none-any.whl", distribution="foo", version="1.0.0")
        info_bar = WheelInfo(path=whl_bar, filename="bar-1.0.0-py3-none-any.whl", distribution="bar", version="1.0.0")
        checker = _make_checker({})
        report = check_conflicts([info_foo, info_bar], checker)
        assert report.has_conflicts
        assert report.conflicts[0].conflict_type == "inter_wheel"
