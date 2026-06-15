"""Install or update the BlenderMCP addon into a local Blender installation.

The addon ships inside this package (``blender_mcp/addon.py``), so a single
``uv tool upgrade blender-mcp`` followed by ``blender-mcp install-addon`` keeps
the MCP server and the Blender addon on the same version. This avoids the manual
download-and-reinstall step and the server/addon version drift it causes.

This module is intentionally dependency-free and its directory-resolution
helpers are pure functions so they can be unit tested without Blender.
"""
from __future__ import annotations

import argparse
import os
import sys
from importlib.resources import files
from pathlib import Path

# Name the installed file distinctly so it does not collide with other
# single-file addons (Blender derives the module name from the filename).
INSTALLED_ADDON_NAME = "blender_mcp_addon.py"
# Marker used to recognize a legacy manual install (addon.py) of this addon.
_ADDON_MARKER = '"name": "Blender MCP"'


def packaged_addon_path() -> Path:
    """Return the path to the addon.py bundled inside this package."""
    return Path(str(files("blender_mcp") / "addon.py"))


def config_base_dirs() -> list[Path]:
    """Return candidate Blender config base directories for this OS.

    Each returned directory is the parent that contains per-version folders
    (for example ``.../Blender/4.1``).
    """
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return [base / "Blender Foundation" / "Blender"]
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "Blender"]
    # Linux and other Unix-likes
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home / ".config"
    return [base / "blender"]


def _version_key(name: str) -> tuple[int, ...] | None:
    """Parse a Blender version folder name like '4.1' into (4, 1).

    Returns None for names that are not dotted numbers, so callers can skip
    unrelated folders.
    """
    parts = name.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def find_blender_versions(base: Path) -> list[Path]:
    """Return version directories under a Blender config base, oldest first."""
    if not base.exists():
        return []
    versioned = []
    for child in base.iterdir():
        if child.is_dir() and _version_key(child.name) is not None:
            versioned.append(child)
    return sorted(versioned, key=lambda p: _version_key(p.name))


def addons_dir(version_dir: Path) -> Path:
    """Return the user addons directory for a Blender version directory."""
    return version_dir / "scripts" / "addons"


def discover_version_dirs() -> list[Path]:
    """Return every detected Blender version directory across base dirs."""
    found: list[Path] = []
    for base in config_base_dirs():
        found.extend(find_blender_versions(base))
    return found


def _looks_like_our_addon(path: Path) -> bool:
    try:
        return _ADDON_MARKER in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def install_into(version_dir: Path, source: Path | None = None) -> Path:
    """Install/overwrite the addon into one Blender version directory.

    Removes a legacy ``addon.py`` copy of this addon in the same folder so the
    user does not end up with two BlenderMCP entries. Returns the written path.
    """
    source = source or packaged_addon_path()
    target_dir = addons_dir(version_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    legacy = target_dir / "addon.py"
    if legacy.exists() and _looks_like_our_addon(legacy):
        legacy.unlink()

    target = target_dir / INSTALLED_ADDON_NAME
    target.write_bytes(source.read_bytes())
    return target


def uninstall_from(version_dir: Path) -> list[Path]:
    """Remove installed copies of the addon from one version directory."""
    target_dir = addons_dir(version_dir)
    removed = []
    for name in (INSTALLED_ADDON_NAME, "addon.py"):
        candidate = target_dir / name
        if candidate.exists() and (name == INSTALLED_ADDON_NAME or _looks_like_our_addon(candidate)):
            candidate.unlink()
            removed.append(candidate)
    return removed


def _select_targets(version_dirs: list[Path], requested: str | None, all_versions: bool) -> list[Path]:
    if not version_dirs:
        return []
    if all_versions:
        return version_dirs
    if requested:
        match = [v for v in version_dirs if v.name == requested]
        return match
    # Default: the newest detected version (version_dirs is sorted ascending).
    return [version_dirs[-1]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="blender-mcp install-addon",
        description="Install or update the BlenderMCP Blender addon.",
    )
    parser.add_argument(
        "--blender-version",
        help="Install into this Blender version only (e.g. 4.1). Default: the newest found.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Install into every detected Blender version.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List detected Blender versions and exit.",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove the addon instead of installing it.",
    )
    args = parser.parse_args(argv)

    version_dirs = discover_version_dirs()

    if args.list:
        if not version_dirs:
            print("No Blender installations found.")
            return 1
        print("Detected Blender versions:")
        for v in version_dirs:
            print(f"  {v.name}  ({addons_dir(v)})")
        return 0

    if not version_dirs:
        bases = ", ".join(str(b) for b in config_base_dirs())
        print(f"No Blender installations found. Looked in: {bases}", file=sys.stderr)
        print("Open Blender once to create its config folder, then retry.", file=sys.stderr)
        return 1

    targets = _select_targets(version_dirs, args.blender_version, args.all)
    if not targets:
        available = ", ".join(v.name for v in version_dirs)
        print(
            f"No matching Blender version. Available: {available}", file=sys.stderr
        )
        return 1

    if args.uninstall:
        any_removed = False
        for version_dir in targets:
            for removed in uninstall_from(version_dir):
                any_removed = True
                print(f"Removed {removed}")
        if not any_removed:
            print("Nothing to remove.")
        return 0

    source = packaged_addon_path()
    if not source.exists():
        print(f"Bundled addon not found at {source}", file=sys.stderr)
        return 1

    for version_dir in targets:
        written = install_into(version_dir, source)
        print(f"Installed BlenderMCP addon -> {written}")
    print(
        "\nEnable it in Blender: Edit > Preferences > Add-ons, search 'Blender MCP', "
        "tick the box. If Blender is already open, restart it first."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
