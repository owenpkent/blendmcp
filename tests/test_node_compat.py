"""Exercise texture material graphs with Blender 3.x, 4.x and 5.x node APIs.

Strict socket names and single-link inputs let these run without Blender while
catching removed node types, renamed sockets, and incorrect channel routing.
"""
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from packaging.requirements import Requirement

from blendmcp import addon
from blendmcp.addon import new_rgb_split_node

ROOT = Path(__file__).resolve().parent.parent


class FakeSockets(list):
    def __getitem__(self, key):
        if isinstance(key, str):
            for socket in self:
                if socket.name == key:
                    return socket
            raise KeyError(key)
        return super().__getitem__(key)


class FakeSocket:
    def __init__(self, node, name):
        self.node = node
        self.name = name
        self.default_value = None
        self.links = []


class FakeNode:
    def __init__(self, node_type, inputs, outputs):
        self.bl_idname = node_type
        self.type = 'TEX_IMAGE' if node_type == 'ShaderNodeTexImage' else node_type
        self.name = node_type
        self.inputs = FakeSockets(FakeSocket(self, name) for name in inputs)
        self.outputs = FakeSockets(FakeSocket(self, name) for name in outputs)
        self.image = None
        self.blend_type = 'MIX'
        if node_type == 'ShaderNodeSeparateColor':
            self.mode = 'RGB'  # Blender's default mode for this node.


class FakeNodes(list):
    """Expose real socket names and reject unavailable Blender node types."""

    def __init__(self, split_types, factor_name='Fac'):
        super().__init__()
        self.layouts = {
            'ShaderNodeOutputMaterial': (['Surface', 'Displacement'], []),
            'ShaderNodeBsdfPrincipled': (
                ['Base Color', 'Metallic', 'Roughness', 'Normal'], ['BSDF'],
            ),
            'ShaderNodeTexCoord': ([], ['Generated', 'Normal', 'UV']),
            'ShaderNodeMapping': (['Vector'], ['Vector']),
            'ShaderNodeTexImage': (['Vector'], ['Color', 'Alpha']),
            'ShaderNodeMixRGB': ([factor_name, 'Color1', 'Color2'], ['Color']),
        }
        split_layouts = {
            'ShaderNodeSeparateRGB': (['Image'], ['R', 'G', 'B']),
            'ShaderNodeSeparateColor': (['Color'], ['Red', 'Green', 'Blue']),
        }
        self.layouts.update({name: split_layouts[name] for name in split_types})

    def new(self, type):
        if type not in self.layouts:
            raise RuntimeError(f"Error: Node type {type} undefined")
        node = FakeNode(type, *self.layouts[type])
        self.append(node)
        return node


class FakeLinks:
    def new(self, output, input):
        assert any(output is socket for socket in output.node.outputs)
        assert any(input is socket for socket in input.node.inputs)
        # Blender replaces an existing link when a single-link input is wired
        # again. This is essential for detecting loss of dedicated-map priority.
        for link in list(input.links):
            self.remove(link)
        link = SimpleNamespace(
            from_socket=output, to_socket=input,
            from_node=output.node, to_node=input.node,
        )
        output.links.append(link)
        input.links.append(link)
        return link

    def remove(self, link):
        link.from_socket.links.remove(link)
        link.to_socket.links.remove(link)


def test_prefers_separate_color_on_modern_blender():
    nodes = FakeNodes({"ShaderNodeSeparateColor", "ShaderNodeSeparateRGB"})
    assert new_rgb_split_node(nodes).bl_idname == "ShaderNodeSeparateColor"
    assert len(nodes) == 1


def test_falls_back_to_separate_rgb_on_old_blender():
    # Blender 3.0-3.2: SeparateColor does not exist yet.
    nodes = FakeNodes({"ShaderNodeSeparateRGB"})
    assert new_rgb_split_node(nodes).bl_idname == "ShaderNodeSeparateRGB"
    assert len(nodes) == 1


def test_blender_5_has_only_separate_color():
    # The regression this guards: Blender 5.x removed SeparateRGB entirely.
    nodes = FakeNodes({"ShaderNodeSeparateColor"})
    assert new_rgb_split_node(nodes).bl_idname == "ShaderNodeSeparateColor"


def test_raises_when_no_node_type_available():
    with pytest.raises(RuntimeError, match="no RGB split node"):
        new_rgb_split_node(FakeNodes(set()))


@pytest.fixture(params=['3.0', '4.x', '5.x'])
def node_api(request):
    split_types = {
        '3.0': {'ShaderNodeSeparateRGB'},
        '4.x': {'ShaderNodeSeparateRGB', 'ShaderNodeSeparateColor'},
        '5.x': {'ShaderNodeSeparateColor'},
    }
    factor_name = 'Factor' if request.param == '5.x' else 'Fac'
    return FakeNodes(split_types[request.param], factor_name), factor_name


def assert_link(source, target):
    assert len(target.links) == 1
    assert target.links[0].from_socket is source
    assert target.links[0].to_socket is target


@pytest.mark.parametrize('maps', [
    pytest.param(['color', 'arm'], id='color-arm'),
    pytest.param(['color', 'arm', 'roughness', 'metallic'], id='dedicated-maps'),
    pytest.param(['color', 'arm', 'roughness'], id='dedicated-roughness'),
    pytest.param(['color', 'arm', 'metallic'], id='dedicated-metallic'),
    pytest.param(['color', 'ao'], id='separate-ao'),
    pytest.param(['arm'], id='arm-without-color'),
])
def test_set_texture_material_graph(monkeypatch, node_api, maps):
    nodes, factor_name = node_api
    material = SimpleNamespace(
        name='stone_material_Cube', use_nodes=False,
        node_tree=SimpleNamespace(nodes=nodes, links=FakeLinks()),
    )
    obj = SimpleNamespace(data=SimpleNamespace(materials=[]), select_set=Mock())
    images = [
        SimpleNamespace(
            name=f'stone_{map_name}', size=(4, 4), file_format='PNG',
            colorspace_settings=SimpleNamespace(name='sRGB'),
            packed_file=True, reload=Mock(),
        )
        for map_name in maps
    ]
    monkeypatch.setattr(addon.bpy, 'data', SimpleNamespace(
        objects={'Cube': obj}, images=images,
        materials=SimpleNamespace(get=lambda name: None, new=lambda name: material),
    ))
    monkeypatch.setattr(addon.bpy, 'context', SimpleNamespace(
        view_layer=SimpleNamespace(objects=SimpleNamespace(active=None), update=Mock()),
    ))

    result = addon.BlendMCPServer().set_texture('Cube', 'stone')

    assert result.get('success') is True, result
    assert obj.data.materials == [material]
    assert material.use_nodes is True
    assert set(result['maps']) == set(maps)
    principled, = [n for n in nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled']
    output, = [n for n in nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
    assert_link(principled.outputs['BSDF'], output.inputs['Surface'])
    textures = {
        n.image.name.removeprefix('stone_'): n
        for n in nodes if n.type == 'TEX_IMAGE'
    }
    splitters = [n for n in nodes if n.bl_idname in {
        'ShaderNodeSeparateColor', 'ShaderNodeSeparateRGB',
    }]
    if 'arm' in maps:
        splitter, = splitters
        if splitter.bl_idname == 'ShaderNodeSeparateColor':
            assert splitter.mode == 'RGB'
            input_name, channels = 'Color', ['Red', 'Green', 'Blue']
        else:
            input_name, channels = 'Image', ['R', 'G', 'B']
        assert_link(textures['arm'].outputs['Color'], splitter.inputs[input_name])
        ao_source, roughness, metallic = [splitter.outputs[name] for name in channels]
        for map_name, target, channel in [
            ('roughness', 'Roughness', roughness),
            ('metallic', 'Metallic', metallic),
        ]:
            source = textures[map_name].outputs['Color'] if map_name in maps else channel
            assert_link(source, principled.inputs[target])
    else:
        assert splitters == []
        assert principled.inputs['Roughness'].links == []
        assert principled.inputs['Metallic'].links == []
        ao_source = textures['ao'].outputs['Color']

    mixes = [n for n in nodes if n.bl_idname == 'ShaderNodeMixRGB']
    if 'color' in maps:
        mix, = mixes
        assert mix.blend_type == 'MULTIPLY'
        assert mix.inputs[factor_name].default_value == pytest.approx(0.8)
        assert_link(textures['color'].outputs['Color'], mix.inputs['Color1'])
        assert_link(ao_source, mix.inputs['Color2'])
        assert_link(mix.outputs['Color'], principled.inputs['Base Color'])
    else:
        assert mixes == []
        assert principled.inputs['Base Color'].links == []
        assert ao_source.links == []


@pytest.mark.parametrize(('version', 'allowed'), [
    ('1.2.9', False),
    ('1.3.0', True),
    ('1.27.2', True),
    ('2.0.0', False),
    ('2.1.0', False),
    ('20.0.0', False),
])
def test_mcp_dependency_excludes_v2(version, allowed):
    """mcp 2.0 renamed FastMCP to MCPServer; server.py targets the v1 API."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    req = Requirement(re.search(r'"(mcp\[cli\][^"]*)"', text).group(1))
    assert (version in req.specifier) is allowed, f"unexpected support for mcp {version}: {req}"
