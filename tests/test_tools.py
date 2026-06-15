"""Unit tests for the MCP tool functions in ``blendmcp.server``.

These exercise each tool's parameter marshalling and result handling against a
fake Blender connection that records the command it received, so no live Blender
is needed. The tools call ``get_blender_connection`` then ``send_command``; we
monkeypatch the former.
"""
import json

import pytest

import blendmcp.server as server


class _Ctx:
    """Placeholder MCP Context; the tools never touch it here."""


class RecordingConn:
    """Fake connection: records the last command and returns a canned response."""

    def __init__(self, response=None, by_command=None):
        self.response = response if response is not None else {"ok": True}
        self.by_command = by_command or {}
        self.calls = []

    def send_command(self, command_type, params=None):
        self.calls.append((command_type, params))
        if command_type in self.by_command:
            return self.by_command[command_type]
        return self.response

    @property
    def last(self):
        return self.calls[-1]


@pytest.fixture
def conn(monkeypatch):
    c = RecordingConn(response={"name": "Cube", "world_bounding_box": [[0, 0, 0], [1, 1, 1]]})
    monkeypatch.setattr(server, "get_blender_connection", lambda: c)
    return c


# --- add_primitive ---

def test_add_primitive_fills_defaults(conn):
    out = server.add_primitive(_Ctx(), primitive_type="SPHERE", name="Ball")
    cmd, params = conn.last
    assert cmd == "add_primitive"
    assert params == {
        "primitive_type": "SPHERE",
        "name": "Ball",
        "location": [0, 0, 0],
        "rotation": [0, 0, 0],
        "scale": [1, 1, 1],
    }
    assert json.loads(out)["name"] == "Cube"


def test_add_primitive_passes_explicit_transform(conn):
    server.add_primitive(_Ctx(), location=[1, 2, 3], rotation=[0, 0, 1], scale=[2, 2, 2])
    _, params = conn.last
    assert params["location"] == [1, 2, 3]
    assert params["rotation"] == [0, 0, 1]
    assert params["scale"] == [2, 2, 2]


# --- modify_object ---

def test_modify_object_sends_only_provided_fields(conn):
    server.modify_object(_Ctx(), name="Cube", location=[1, 0, 0])
    cmd, params = conn.last
    assert cmd == "modify_object"
    assert params == {"name": "Cube", "location": [1, 0, 0]}


def test_modify_object_includes_visible_false(conn):
    server.modify_object(_Ctx(), name="Cube", visible=False)
    _, params = conn.last
    assert params == {"name": "Cube", "visible": False}


# --- delete_object ---

def test_delete_object(conn):
    server.delete_object(_Ctx(), name="Cube")
    assert conn.last == ("delete_object", {"name": "Cube"})


# --- set_material ---

def test_set_material_normalizes_color_and_omits_unset(conn):
    server.set_material(_Ctx(), object_name="Cube", color=[1, 0, 0], roughness=0.3)
    cmd, params = conn.last
    assert cmd == "set_material"
    assert params["object_name"] == "Cube"
    assert params["color"] == [1.0, 0.0, 0.0, 1.0]
    assert params["roughness"] == 0.3
    assert "metallic" not in params
    assert "material_name" not in params


def test_set_material_rejects_bad_color(conn):
    out = server.set_material(_Ctx(), object_name="Cube", color=[2, 0, 0])
    assert out.startswith("Error setting material")
    # invalid color is caught before any command is sent
    assert conn.calls == []


# --- duplicate_object ---

def test_duplicate_object_default_offset(conn):
    server.duplicate_object(_Ctx(), name="Cube")
    cmd, params = conn.last
    assert cmd == "duplicate_object"
    assert params == {"name": "Cube", "new_name": None, "offset": [0, 0, 0]}


# --- error handling shared shape ---

def test_tool_returns_error_string_on_failure(monkeypatch):
    class Boom:
        def send_command(self, *a, **k):
            raise Exception("no connection")

    monkeypatch.setattr(server, "get_blender_connection", lambda: Boom())
    out = server.add_primitive(_Ctx(), primitive_type="CUBE")
    assert out.startswith("Error adding primitive")


# --- get_blender_status ---

def test_get_blender_status_disconnected(monkeypatch):
    def boom():
        raise Exception("Could not connect to Blender")

    monkeypatch.setattr(server, "get_blender_connection", boom)
    out = json.loads(server.get_blender_status(_Ctx()))
    assert out["connected"] is False
    assert out["server_version"]  # always reported
    assert "addon" in out["hint"].lower() or "blender" in out["hint"].lower()


def test_get_blender_status_reports_stale_addon(monkeypatch):
    responses = {
        "get_addon_version": {"version": [1, 2, 0]},
        "get_polyhaven_status": {"enabled": True},
        "get_hyper3d_status": {"enabled": False},
        "get_sketchfab_status": {"enabled": False},
        "get_hunyuan3d_status": {"message": "disabled"},
    }
    conn = RecordingConn(by_command=responses)
    monkeypatch.setattr(server, "get_blender_connection", lambda: conn)
    monkeypatch.setattr(server, "_server_version", lambda: "1.4.0")

    out = json.loads(server.get_blender_status(_Ctx()))
    assert out["connected"] is True
    assert out["addon_version"] == [1, 2, 0]
    assert out["integrations"]["polyhaven"] is True
    assert out["integrations"]["hyper3d"] is False
    assert out["integrations"]["hunyuan3d"] == "unknown"  # only a message, no 'enabled'
    assert out["hint"] is not None and "install-addon" in out["hint"]


def test_get_blender_status_current_addon_no_hint(monkeypatch):
    responses = {
        "get_addon_version": {"version": [1, 4, 0]},
        "get_polyhaven_status": {"enabled": False},
        "get_hyper3d_status": {"enabled": False},
        "get_sketchfab_status": {"enabled": False},
        "get_hunyuan3d_status": {"message": ""},
    }
    conn = RecordingConn(by_command=responses)
    monkeypatch.setattr(server, "get_blender_connection", lambda: conn)
    monkeypatch.setattr(server, "_server_version", lambda: "1.4.0")

    out = json.loads(server.get_blender_status(_Ctx()))
    assert out["connected"] is True
    assert out["addon_version"] == [1, 4, 0]
    assert out["hint"] is None
