"""Test fixtures for blendmcp.

addon.py is a single-file Blender addon that imports ``bpy`` and ``mathutils``
at module scope, so it cannot normally be imported outside Blender. To unit
test the pure geometry helpers it exposes, we install lightweight fakes for
those modules into ``sys.modules`` before any test imports ``addon``.

The fakes only need to make ``import addon`` succeed:
- ``bpy.types.<Name>`` must be a real, subclassable base class.
- ``bpy.props.<Name>`` must be a callable usable as a property annotation.
- ``bpy.utils`` / ``bpy.app`` / ``bpy.context`` / ``bpy.ops`` are only touched
  at call time, so a MagicMock is sufficient.
- ``mathutils`` is only used inside methods, never at import.
"""
import os
import sys
import types
from unittest.mock import MagicMock

# Make the repo root importable (pytest only puts the tests/ dir on sys.path by
# default). The addon now ships inside the package as ``blendmcp.addon``.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _install_fake_bpy():
    if "bpy" in sys.modules:
        return

    bpy = types.ModuleType("bpy")

    # bpy.types: every attribute access yields a distinct, subclassable class.
    bpy_types = types.ModuleType("bpy.types")
    _type_cache = {}

    def _types_getattr(name):
        if name not in _type_cache:
            _type_cache[name] = type(name, (object,), {})
        return _type_cache[name]

    bpy_types.__getattr__ = _types_getattr

    # bpy.props: every attribute is a no-op property factory.
    bpy_props = types.ModuleType("bpy.props")

    def _prop_factory(*args, **kwargs):
        return None

    bpy_props.__getattr__ = lambda name: _prop_factory
    for _name in (
        "IntProperty", "BoolProperty", "StringProperty", "FloatProperty",
        "EnumProperty", "FloatVectorProperty", "PointerProperty",
        "CollectionProperty",
    ):
        setattr(bpy_props, _name, _prop_factory)

    bpy.types = bpy_types
    bpy.props = bpy_props
    bpy.utils = MagicMock(name="bpy.utils")
    bpy.app = MagicMock(name="bpy.app")
    bpy.context = MagicMock(name="bpy.context")
    bpy.ops = MagicMock(name="bpy.ops")
    bpy.data = MagicMock(name="bpy.data")

    sys.modules["bpy"] = bpy
    sys.modules["bpy.types"] = bpy_types
    sys.modules["bpy.props"] = bpy_props

    mathutils = types.ModuleType("mathutils")
    mathutils.Vector = MagicMock(name="mathutils.Vector")
    sys.modules["mathutils"] = mathutils

    # requests ships with Blender's bundled Python, not as a project
    # dependency. addon.py only uses it at import time to build a headers dict
    # and in runtime except-clauses these tests never reach, so a mock suffices.
    if "requests" not in sys.modules:
        sys.modules["requests"] = MagicMock(name="requests")


_install_fake_bpy()
