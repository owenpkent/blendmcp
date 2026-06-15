"""Tests for the pure helpers and connection behavior in ``mcpblender.server``.

These cover color normalization, bounding-box ratio processing, environment
config loading, the reconnect-once-and-retry logic, and the tool-level handling
of structured code-execution errors and batch color normalization. None of them
need a live Blender, so they run with fakes.
"""
import json
import socket

import pytest

import mcpblender.server as server
from mcpblender.server import (
    BlenderConnection,
    MCPBlenderConfig,
    _addon_staleness,
    _normalize_rgba,
    _process_bbox,
    _wait_for_stable_file,
)


class _FakeSock:
    """Minimal stand-in for a connected socket."""

    def sendall(self, data):
        pass

    def settimeout(self, timeout):
        pass

    def close(self):
        pass


class _Ctx:
    """Placeholder MCP Context; the tools never touch it in these tests."""


def test_normalize_rgba_none_passes_through():
    assert _normalize_rgba(None) is None


def test_normalize_rgba_pads_rgb_to_rgba():
    assert _normalize_rgba([1, 0, 0]) == [1.0, 0.0, 0.0, 1.0]


def test_normalize_rgba_preserves_alpha():
    assert _normalize_rgba([0.2, 0.4, 0.6, 0.5]) == [0.2, 0.4, 0.6, 0.5]


def test_normalize_rgba_casts_ints_to_floats():
    result = _normalize_rgba([0, 1, 0])
    assert result == [0.0, 1.0, 0.0, 1.0]
    assert all(isinstance(c, float) for c in result)


@pytest.mark.parametrize("bad", [[1, 2], [1, 1, 1, 1, 1], "red", 5])
def test_normalize_rgba_rejects_wrong_shape(bad):
    with pytest.raises(ValueError):
        _normalize_rgba(bad)


@pytest.mark.parametrize("bad", [[1.5, 0, 0], [-0.1, 0, 0], [0, 0, 2]])
def test_normalize_rgba_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        _normalize_rgba(bad)


def test_process_bbox_none_passes_through():
    assert _process_bbox(None) is None


def test_process_bbox_all_ints_unchanged():
    assert _process_bbox([1, 2, 4]) == [1, 2, 4]


def test_process_bbox_floats_normalized_to_percent_of_max():
    assert _process_bbox([1.0, 2.0, 4.0]) == [25, 50, 100]


def test_process_bbox_rejects_non_positive_floats():
    with pytest.raises(ValueError):
        _process_bbox([0.0, 1.0, 2.0])


# --- MCPBlenderConfig.from_env ---

def test_config_defaults(monkeypatch):
    monkeypatch.delenv("BLENDER_HOST", raising=False)
    monkeypatch.delenv("BLENDER_PORT", raising=False)
    cfg = MCPBlenderConfig.from_env()
    assert cfg.host == "localhost"
    assert cfg.port == 9876


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("BLENDER_HOST", "1.2.3.4")
    monkeypatch.setenv("BLENDER_PORT", "9999")
    cfg = MCPBlenderConfig.from_env()
    assert cfg.host == "1.2.3.4"
    assert cfg.port == 9999


def test_config_malformed_port_falls_back(monkeypatch):
    monkeypatch.setenv("BLENDER_PORT", "not-a-number")
    cfg = MCPBlenderConfig.from_env()
    assert cfg.port == 9876  # default, not a crash


# --- reconnect-once-and-retry ---

def _connection_with_recv(recv_fn):
    conn = BlenderConnection(host="h", port=1)
    conn.sock = _FakeSock()
    conn.connect = lambda timeout=5.0: (setattr(conn, "sock", _FakeSock()) or True)
    conn.receive_full_response = recv_fn
    return conn


def test_send_command_retries_once_on_connection_error():
    calls = {"n": 0}

    def recv(sock, buffer_size=8192):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionResetError("socket died")
        return json.dumps({"status": "success", "result": {"ok": True}}).encode()

    conn = _connection_with_recv(recv)
    assert conn.send_command("get_scene_info") == {"ok": True}
    assert calls["n"] == 2  # original attempt + one retry


def test_send_command_does_not_retry_on_timeout():
    calls = {"n": 0}

    def recv(sock, buffer_size=8192):
        calls["n"] += 1
        raise socket.timeout()

    conn = _connection_with_recv(recv)
    with pytest.raises(Exception):
        conn.send_command("execute_code", {"code": "x"})
    assert calls["n"] == 1  # not retried; Blender may still be running it


# --- execute_blender_code structured failure ---

def test_execute_blender_code_surfaces_traceback(monkeypatch):
    class FakeConn:
        def send_command(self, cmd, params=None):
            return {
                "executed": False,
                "result": "partial output",
                "error": "NameError: name 'foo' is not defined",
                "traceback": "Traceback (most recent call last):\nNameError: ...",
            }

    monkeypatch.setattr(server, "get_blender_connection", lambda: FakeConn())
    out = server.execute_blender_code(_Ctx(), code="foo()")
    assert "Code execution failed" in out
    assert "NameError" in out
    assert "Traceback" in out
    assert "partial output" in out


# --- batch_edit color normalization ---

def test_batch_edit_normalizes_material_colors(monkeypatch):
    captured = {}

    class FakeConn:
        def send_command(self, cmd, params=None):
            captured["params"] = params
            return {"total": 1, "applied": 1, "failed": 0, "results": []}

    monkeypatch.setattr(server, "get_blender_connection", lambda: FakeConn())
    ops = [
        {"op": "set_material", "object_name": "Cube", "color": [1, 0, 0]},
        {"op": "modify_object", "name": "Cube", "location": [1, 2, 3]},
    ]
    server.batch_edit(_Ctx(), operations=ops)
    sent = captured["params"]["operations"]
    assert sent[0]["color"] == [1.0, 0.0, 0.0, 1.0]  # padded to RGBA
    assert sent[1] == {"op": "modify_object", "name": "Cube", "location": [1, 2, 3]}


# --- screenshot file-stability wait ---

def test_wait_for_stable_file_true_for_existing_file(tmp_path):
    f = tmp_path / "shot.png"
    f.write_bytes(b"some bytes")
    assert _wait_for_stable_file(str(f), timeout=1.0) is True


def test_wait_for_stable_file_false_when_missing(tmp_path):
    missing = tmp_path / "nope.png"
    assert _wait_for_stable_file(str(missing), timeout=0.2) is False


# --- addon staleness (version handshake) ---

def test_addon_staleness_none_when_current():
    assert _addon_staleness("1.4.0", [1, 4, 0]) is None


def test_addon_staleness_none_when_addon_newer():
    assert _addon_staleness("1.4.0", [1, 5, 0]) is None


def test_addon_staleness_hint_when_older():
    hint = _addon_staleness("1.4.0", [1, 2, 0])
    assert hint is not None
    assert "install-addon" in hint


def test_addon_staleness_hint_when_version_unknown():
    hint = _addon_staleness("1.4.0", None)
    assert hint is not None
    assert "install-addon" in hint


def test_addon_staleness_uncomparable_returns_none():
    # A source checkout reports an unparseable server version; do not warn.
    assert _addon_staleness("unknown", [1, 4, 0]) is None
