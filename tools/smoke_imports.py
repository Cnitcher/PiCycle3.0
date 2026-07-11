#!/usr/bin/env python3
"""Local dependency smoke gate for PiCycle.

Default mode validates that pyproject.toml declares the expected import groups and
reports what is installed. It does not require Raspberry Pi hardware libraries.
Use --strict-installed after installing dependencies to require selected groups.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
GROUPS = ("core", "prototype", "hardware")


def load_groups() -> dict[str, list[str]]:
    smoke: dict[str, list[str]] = {}
    current_group: str | None = None
    in_smoke_table = False

    for raw_line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_smoke_table = line == "[tool.picycle.smoke_imports]"
            current_group = None
            continue
        if not in_smoke_table:
            continue
        if "=" in line and line.endswith("["):
            current_group = line.split("=", 1)[0].strip()
            smoke[current_group] = []
            continue
        if current_group and line == "]":
            current_group = None
            continue
        if current_group:
            module = line.rstrip(",").strip().strip('"')
            if module:
                smoke[current_group].append(module)

    missing = [group for group in GROUPS if group not in smoke]
    if missing:
        raise SystemExit(f"pyproject.toml is missing smoke import group(s): {', '.join(missing)}")
    return {group: list(smoke[group]) for group in GROUPS}


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def print_group(name: str, modules: list[str]) -> list[str]:
    print(f"{name}:")
    missing: list[str] = []
    for module in modules:
        present = module_available(module)
        status = "ok" if present else "missing"
        print(f"  {status:7} {module}")
        if not present:
            missing.append(module)
    return missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check PiCycle dependency groups.")
    parser.add_argument(
        "--strict-installed",
        action="store_true",
        help="Fail if selected non-hardware groups are not installed.",
    )
    parser.add_argument(
        "--include-hardware",
        action="store_true",
        help="Include Raspberry Pi hardware imports in strict installed checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    groups = load_groups()

    print(f"Python: {sys.version.split()[0]}")
    print(f"Project: {ROOT}")
    print("")

    missing_by_group = {name: print_group(name, groups[name]) for name in GROUPS}

    if args.strict_installed:
        strict_groups = ["core", "prototype"]
        if args.include_hardware:
            strict_groups.append("hardware")
        strict_missing = {
            group: missing_by_group[group]
            for group in strict_groups
            if missing_by_group[group]
        }
        if strict_missing:
            print("")
            print("Strict check failed. Install dependencies with:")
            print("  python -m pip install -e .[prototype]")
            print("For Raspberry Pi hardware support, also install:")
            print("  python -m pip install -e .[hardware]")
            return 1

    print("")
    print("Smoke manifest check passed.")
    if missing_by_group["hardware"]:
        print("Hardware imports are optional for desktop/prototype development.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
