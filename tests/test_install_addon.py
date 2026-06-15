"""Tests for the addon installer helpers and version consistency.

The directory-resolution and selection helpers in ``mcpblender.install_addon``
are pure functions, so they run against temporary directories without Blender.
A guard test also asserts the addon's ``bl_info`` version matches the package
version so the two cannot silently drift again.
"""
import re
from pathlib import Path

import pytest

from mcpblender import install_addon as ia

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
    legacy.write_text('bl_info = {"name": "BlendMCP"}\n', encoding="utf-8")

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
    text = (ROOT / "src" / "mcpblender" / "addon.py").read_text(encoding="utf-8")
    nums = re.search(r'"version":\s*\(([^)]+)\)', text).group(1)
    return ".".join(p.strip() for p in nums.split(","))


def test_addon_version_matches_package():
    # If this fails, bump bl_info["version"] in addon.py to match pyproject.
    assert _version_from_addon() == _version_from_pyproject()


# --- main() CLI flow (no Blender needed; fake config tree) ---

@pytest.fixture
def fake_blender(tmp_path, monkeypatch):
    """Point the installer at a temp tree with Blender 4.1 and 4.2."""
    base = tmp_path / "Blender"
    for name in ["4.1", "4.2"]:
        (base / name).mkdir(parents=True)
    monkeypatch.setattr(ia, "config_base_dirs", lambda: [base])
    return base


def test_main_list(fake_blender, capsys):
    rc = ia.main(["--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "4.1" in out and "4.2" in out


def test_main_list_no_blender(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ia, "config_base_dirs", lambda: [tmp_path / "absent"])
    rc = ia.main(["--list"])
    assert rc == 1
    assert "No Blender" in capsys.readouterr().out


def test_main_install_default_targets_newest(fake_blender):
    rc = ia.main([])
    assert rc == 0
    assert (fake_blender / "4.2" / "scripts" / "addons" / ia.INSTALLED_ADDON_NAME).exists()
    # default install does not touch the older version
    assert not (fake_blender / "4.1" / "scripts" / "addons" / ia.INSTALLED_ADDON_NAME).exists()


def test_main_install_all(fake_blender):
    rc = ia.main(["--all"])
    assert rc == 0
    for v in ["4.1", "4.2"]:
        assert (fake_blender / v / "scripts" / "addons" / ia.INSTALLED_ADDON_NAME).exists()


def test_main_install_specific_version(fake_blender):
    rc = ia.main(["--blender-version", "4.1"])
    assert rc == 0
    assert (fake_blender / "4.1" / "scripts" / "addons" / ia.INSTALLED_ADDON_NAME).exists()
    assert not (fake_blender / "4.2" / "scripts" / "addons" / ia.INSTALLED_ADDON_NAME).exists()


def test_main_install_unknown_version_fails(fake_blender, capsys):
    rc = ia.main(["--blender-version", "9.9"])
    assert rc == 1
    assert "No matching Blender version" in capsys.readouterr().err


def test_main_install_then_uninstall(fake_blender):
    ia.main(["--all"])
    rc = ia.main(["--all", "--uninstall"])
    assert rc == 0
    for v in ["4.1", "4.2"]:
        assert not (fake_blender / v / "scripts" / "addons" / ia.INSTALLED_ADDON_NAME).exists()


def test_main_install_no_blender_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ia, "config_base_dirs", lambda: [tmp_path / "absent"])
    rc = ia.main([])
    assert rc == 1
    assert "No Blender installations found" in capsys.readouterr().err
