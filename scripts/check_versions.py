#!/usr/bin/env python3
"""Validate that package and plugin versions are consistent."""

import re
import sys
from pathlib import Path


def extract(pattern, text, source):
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Could not find version in {source}")
    return match.group(1)


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def main():
    versions = {
        "pyproject.toml": extract(
            r'^version\s*=\s*"([^"]+)"', read_text("pyproject.toml"), "pyproject.toml"
        ),
        "setup.py": extract(
            r'version\s*=\s*"([^"]+)"', read_text("setup.py"), "setup.py"
        ),
        "__init__.py": extract(
            r'__plugin_version__\s*=\s*"([^"]+)"',
            read_text("__init__.py"),
            "__init__.py",
        ),
    }

    unique_versions = sorted(set(versions.values()))
    if len(unique_versions) != 1:
        print("Version mismatch detected:", file=sys.stderr)
        for source, version in versions.items():
            print(f"  - {source}: {version}", file=sys.stderr)
        return 1

    version = unique_versions[0]
    print(f"Version check passed: {version}")
    print(f"Expected release tag: v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())