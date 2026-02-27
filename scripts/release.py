#!/usr/bin/env python3
"""Release script for saorsa-deploy.

Creates a chore(release) commit with the new version, tags it, and pushes to the
maidsafe upstream repository.

Usage:
    uv run scripts/release.py 0.2.0
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAIDSAFE_PATTERN = "maidsafe/saorsa-deploy"


def fail(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, **kwargs)
    if result.returncode != 0:
        fail(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result


def get_current_version() -> str:
    text = PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"(.+?)"', text, re.MULTILINE)
    if not match:
        fail("Could not find version in pyproject.toml")
    return match.group(1)


def update_version(new_version: str) -> None:
    text = PYPROJECT.read_text()
    updated = re.sub(
        r'^(version\s*=\s*)"(.+?)"',
        f'\\1"{new_version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT.write_text(updated)


def find_maidsafe_remote() -> str:
    result = run(["git", "remote", "-v"])
    for remote_name in ["origin", "upstream"]:
        for line in result.stdout.splitlines():
            if line.startswith(remote_name) and MAIDSAFE_PATTERN in line:
                return remote_name
    fail(
        f"No remote found pointing to {MAIDSAFE_PATTERN}.\n"
        "Expected either 'origin' or 'upstream' to point to the maidsafe repository."
    )


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <version>", file=sys.stderr)
        sys.exit(1)

    new_version = sys.argv[1]
    if not SEMVER_RE.match(new_version):
        fail(f"Invalid version '{new_version}'. Expected semver format: X.Y.Z")

    current_version = get_current_version()
    tag = f"v{new_version}"

    print(f"Current version: {current_version}")
    print(f"New version:     {new_version}")
    print(f"Tag:             {tag}")

    remote = find_maidsafe_remote()
    print(f"Target remote:   {remote}")
    print()

    # Update pyproject.toml
    update_version(new_version)
    print(f"Updated pyproject.toml: {current_version} -> {new_version}")

    # Regenerate uv.lock with new version
    run(["uv", "lock"])
    print("Updated uv.lock")

    # Create commit
    run(["git", "add", "pyproject.toml", "uv.lock"])
    run(["git", "commit", "-m", f"chore(release): {tag}"])
    print(f"Created commit: chore(release): {tag}")

    # Create tag
    run(["git", "tag", tag])
    print(f"Created tag: {tag}")

    # Push commit and tag
    run(["git", "push", remote, "main"])
    run(["git", "push", remote, tag])
    print(f"Pushed to {remote}/main with tag {tag}")


if __name__ == "__main__":
    main()
