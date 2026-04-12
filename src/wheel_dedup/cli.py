import argparse
import sys
from typing import List, Tuple

from .checker import InstalledChecker
from .conflict import ConflictReport, check_conflicts
from .installer import InstallResult, install_wheel
from .parser import parse_wheel, WheelInfo


def _collect_wheels(paths: List[str]) -> List[str]:
    import glob

    result = []
    for p in paths:
        expanded = glob.glob(p)
        if expanded:
            result.extend(expanded)
        else:
            result.append(p)
    return result


def _analyze(
    wheel_paths: List[str], checker: InstalledChecker
) -> Tuple[List[Tuple[WheelInfo, str]], List[WheelInfo]]:
    skipped: List[Tuple[WheelInfo, str]] = []
    to_install: List[WheelInfo] = []

    for path in wheel_paths:
        try:
            info = parse_wheel(path)
        except ValueError as e:
            print(f"  ERROR {path} ({e})", file=sys.stderr)
            continue

        version = checker.get_installed_version(info.normalized_name)
        if version is not None:
            skipped.append((info, version))
        else:
            to_install.append(info)

    return skipped, to_install


def _confirm(message: str, yes: bool) -> bool:
    if yes:
        return True
    try:
        answer = input(f"{message} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer == "y"


def _print_conflicts(report: ConflictReport) -> None:
    type_labels = {
        "installed_mismatch": "VERSION MISMATCH",
        "inter_wheel": "WHEEL CONFLICT",
        "missing": "MISSING DEPENDENCY",
    }
    for c in report.conflicts:
        label = type_labels.get(c.conflict_type, "CONFLICT")
        print(f"  {label}: {c.detail}")


def cmd_install(args: argparse.Namespace) -> int:
    wheel_paths = _collect_wheels(args.wheels)
    if not wheel_paths:
        print("No wheel files specified.", file=sys.stderr)
        return 1

    checker = InstalledChecker()
    print(f"Checking {len(wheel_paths)} wheel file(s)...")

    skipped, to_install = _analyze(wheel_paths, checker)

    for info, ver in skipped:
        print(f"  SKIP   {info.filename} ({info.normalized_name} {ver} already installed)")

    for info in to_install:
        print(f"  INSTALL {info.filename}")

    print(f"\n{len(skipped)} skipped, {len(to_install)} to install")

    if args.dry_run:
        if not args.skip_conflict_check and to_install:
            print("\nChecking for version conflicts...")
            report = check_conflicts(to_install, checker)
            if report.has_conflicts:
                _print_conflicts(report)
                print(f"\n{len(report.conflicts)} conflict(s) found")
            else:
                print("  No conflicts detected")
        return 0

    if not args.skip_conflict_check and to_install:
        print("\nChecking for version conflicts...")
        report = check_conflicts(to_install, checker)
        if report.has_conflicts:
            _print_conflicts(report)
            if not _confirm(
                f"\n{len(report.conflicts)} conflict(s) found. Continue anyway?",
                args.yes,
            ):
                print("Aborted.")
                return 0
        else:
            print("  No conflicts detected")

    if not to_install:
        return 0

    if not _confirm(f"\n{len(to_install)} to install. Continue?", args.yes):
        print("Aborted.")
        return 0

    results: List[InstallResult] = []
    for info in to_install:
        print(f"\nInstalling {info.filename}...", end=" ")
        res = install_wheel(info.path, verbose=args.verbose)
        results.append(res)
        status = "OK" if res.success else f"FAILED: {res.message}"
        print(status)

    installed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    print(f"\nDone: {installed} installed, {len(skipped)} skipped, {failed} failed")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wheel-dedup",
        description="Install wheel files, skipping already-installed packages",
    )
    sub = parser.add_subparsers(dest="command")

    install_parser = sub.add_parser("install", help="Install wheel files with dedup")
    install_parser.add_argument("wheels", nargs="+", help="Wheel file path(s)")
    install_parser.add_argument(
        "--dry-run", action="store_true", help="Only show what would be done"
    )
    install_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )
    install_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show pip install output"
    )
    install_parser.add_argument(
        "--skip-conflict-check",
        action="store_true",
        help="Skip version conflict detection",
    )
    install_parser.set_defaults(func=cmd_install)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
