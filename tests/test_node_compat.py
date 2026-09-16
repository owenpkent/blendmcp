"""Tests for the shader-node compatibility helper in the addon.

Blender 5.0 removed ``ShaderNodeSeparateRGB`` in favour of
``ShaderNodeSeparateColor`` (added in 3.3), so the addon has to pick whichever
one the running Blender provides. ``bpy`` is faked in conftest, so these tests
drive the helper with a stub node collection that mimics either Blender.
"""
import re
from pathlib import Path

import pytest

from blendmcp.addon import new_rgb_split_node

ROOT = Path(__file__).resolve().parent.parent


class FakeNodes:
    """Stub of ``node_tree.nodes``; rejects any type not in ``available``.

    Blender raises RuntimeError from ``nodes.new`` for an unknown node type.
    """

    def __init__(self, available):
        self.available = set(available)
        self.created = []

    def new(self, type):
        if type not in self.available:
            raise RuntimeError(f"Error: Node type {type} undefined")
        self.created.append(type)
        return f"<node {type}>"


def test_prefers_separate_color_on_modern_blender():
    nodes = FakeNodes({"ShaderNodeSeparateColor", "ShaderNodeSeparateRGB"})
    assert new_rgb_split_node(nodes) == "<node ShaderNodeSeparateColor>"
    assert nodes.created == ["ShaderNodeSeparateColor"]


def test_falls_back_to_separate_rgb_on_old_blender():
    # Blender 3.0-3.2: SeparateColor does not exist yet.
    nodes = FakeNodes({"ShaderNodeSeparateRGB"})
    assert new_rgb_split_node(nodes) == "<node ShaderNodeSeparateRGB>"
    assert nodes.created == ["ShaderNodeSeparateRGB"]


def test_blender_5_has_only_separate_color():
    # The regression this guards: Blender 5.x removed SeparateRGB entirely.
    nodes = FakeNodes({"ShaderNodeSeparateColor"})
    assert new_rgb_split_node(nodes) == "<node ShaderNodeSeparateColor>"


def test_raises_when_no_node_type_available():
    with pytest.raises(RuntimeError, match="no RGB split node"):
        new_rgb_split_node(FakeNodes(set()))


def test_addon_does_not_reference_removed_node_type():
    """The addon must not create SeparateRGB outside the fallback tuple.

    Matches the quoted node-type literal, so prose in comments is not flagged.
    """
    text = (ROOT / "src" / "blendmcp" / "addon.py").read_text(encoding="utf-8")
    literal = re.compile(r"""['"]ShaderNodeSeparateRGB['"]""")
    hits = [
        line.strip() for line in text.splitlines()
        if literal.search(line) and "_RGB_SPLIT_NODE_TYPES" not in line
    ]
    assert hits == [], f"hardcoded removed node type: {hits}"


def test_mix_factor_socket_addressed_by_index():
    """'Fac' was renamed to 'Factor' in Blender 5.0; index 0 works on both."""
    text = (ROOT / "src" / "blendmcp" / "addon.py").read_text(encoding="utf-8")
    assert "inputs['Fac']" not in text
    assert 'inputs["Fac"]' not in text


def test_mcp_dependency_excludes_v2():
    """mcp 2.0 renamed FastMCP to MCPServer; server.py targets the v1 API."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    req = re.search(r'"(mcp\[cli\][^"]*)"', text).group(1)
    assert "<2" in req, f"mcp requirement must be capped below 2.0: {req!r}"
