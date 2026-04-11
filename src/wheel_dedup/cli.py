import argparse
import sys
from typing import List, Tuple

from .checker import InstalledChecker
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


def _confirm(num_install: int, yes: bool) -> bool:
    if yes or num_install == 0:
        return True
    try:
        answer = input(f"\n{num_install} to install. Continue? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer == "y"


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
        return 0

    if not _confirm(len(to_install), args.yes):
        print("Aborted.")
        return 0

    results: List[InstallResult] = []
    for info in to_install:
        print(f"\nInstalling {info.filename}...", end=" ")
        res = install_wheel(info.filename, verbose=args.verbose)
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
