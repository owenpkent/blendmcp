"""Tests for the addon installer helpers and version consistency.

The directory-resolution and selection helpers in ``blender_mcp.install_addon``
are pure functions, so they run against temporary directories without Blender.
A guard test also asserts the addon's ``bl_info`` version matches the package
version so the two cannot silently drift again.
"""
import os
import re
from pathlib import Path

os.environ.setdefault("DISABLE_TELEMETRY", "1")

import pytest

from blender_mcp import install_addon as ia

ROOT = Path(__file__).resolve().parent.parent


def test_packaged_addon_exists():
    p = ia.packaged_addon_path()
    assert p.exists()
    assert p.stat().st_size > 1000


@pytest.mark.parametrize(
    "name,expected",
    [("4.1", (4, 1)), ("3.6", (3, 6)), ("5.0", (5, 0)), ("notes", None), ("", None)],
)
def test_version_key(name, expected):
    assert ia._version_key(name) == expected


def test_find_blender_versions_sorted_and_filtered(tmp_path):
    base = tmp_path / "Blender"
    for name in ["3.6", "4.10", "4.2", "addons", "config"]:
        (base / name).mkdir(parents=True)
    found = [p.name for p in ia.find_blender_versions(base)]
    # numeric sort (4.10 > 4.2), non-version folders skipped
    assert found == ["3.6", "4.2", "4.10"]


def test_find_blender_versions_missing_base(tmp_path):
    assert ia.find_blender_versions(tmp_path / "nope") == []


def test_select_targets_defaults_to_newest(tmp_path):
    base = tmp_path / "Blender"
    for name in ["3.6", "4.1", "4.2"]:
        (base / name).mkdir(parents=True)
    versions = ia.find_blender_versions(base)
    assert [p.name for p in ia._select_targets(versions, None, False)] == ["4.2"]
    assert [p.name for p in ia._select_targets(versions, None, True)] == ["3.6", "4.1", "4.2"]
    assert [p.name for p in ia._select_targets(versions, "4.1", False)] == ["4.1"]
    assert ia._select_targets(versions, "9.9", False) == []


def test_install_and_uninstall_roundtrip(tmp_path):
    version_dir = tmp_path / "4.2"
    version_dir.mkdir()
    written = ia.install_into(version_dir, ia.packaged_addon_path())
    assert written.name == ia.INSTALLED_ADDON_NAME
    assert written.parent == version_dir / "scripts" / "addons"
    assert written.read_bytes() == ia.packaged_addon_path().read_bytes()

    removed = ia.uninstall_from(version_dir)
    assert written in removed
    assert not written.exists()


def test_install_removes_legacy_addon_copy(tmp_path):
    version_dir = tmp_path / "4.2"
    addons = version_dir / "scripts" / "addons"
    addons.mkdir(parents=True)
    legacy = addons / "addon.py"
    legacy.write_text('bl_info = {"name": "Blender MCP"}\n', encoding="utf-8")

    ia.install_into(version_dir, ia.packaged_addon_path())
    # The legacy single-file copy is removed so Blender shows one addon, not two.
    assert not legacy.exists()
    assert (addons / ia.INSTALLED_ADDON_NAME).exists()


def test_config_base_dirs_windows(monkeypatch):
    monkeypatch.setattr(ia.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\Test\AppData\Roaming")
    bases = ia.config_base_dirs()
    assert bases == [Path(r"C:\Users\Test\AppData\Roaming") / "Blender Foundation" / "Blender"]


def test_config_base_dirs_linux_uses_xdg(monkeypatch):
    monkeypatch.setattr(ia.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/test/.config")
    bases = ia.config_base_dirs()
    assert bases == [Path("/home/test/.config") / "blender"]


def _version_from_pyproject() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1)


def _version_from_addon() -> str:
    text = (ROOT / "src" / "blender_mcp" / "addon.py").read_text(encoding="utf-8")
    nums = re.search(r'"version":\s*\(([^)]+)\)', text).group(1)
    return ".".join(p.strip() for p in nums.split(","))


def test_addon_version_matches_package():
    # If this fails, bump bl_info["version"] in addon.py to match pyproject.
    assert _version_from_addon() == _version_from_pyproject()
