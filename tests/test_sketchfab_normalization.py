"""Tests for the Sketchfab model size-normalization geometry.

These exercise the pure helpers extracted from
``BlendMCPServer.download_sketchfab_model`` in addon.py. They cover the
combined bounding-box reduction, dimension calculation, and the scale factor
that maps a model's largest dimension onto a requested target size. The fake
``bpy``/``mathutils`` modules in conftest.py let ``addon`` import outside
Blender.
"""
import math

from blendmcp import addon


def test_addon_imports_outside_blender():
    # Smoke test: importing the single-file addon must not require Blender.
    assert hasattr(addon, "_combine_world_bounds")
    assert hasattr(addon, "_bounds_dimensions")
    assert hasattr(addon, "_normalization_scale")


def test_combine_world_bounds_basic():
    corners = [(0, 0, 0), (2, 3, 4), (1, -1, 0)]
    mn, mx = addon._combine_world_bounds(corners)
    assert mn == (0, -1, 0)
    assert mx == (2, 3, 4)


def test_combine_world_bounds_consumes_iterator():
    # download_sketchfab_model passes a generator; ensure that works.
    corners = iter([(0, 0, 0), (-5, 1, 2), (3, 3, -1)])
    mn, mx = addon._combine_world_bounds(corners)
    assert mn == (-5, 0, -1)
    assert mx == (3, 3, 2)


def test_combine_world_bounds_empty_returns_none():
    assert addon._combine_world_bounds([]) is None


def test_bounds_dimensions():
    assert addon._bounds_dimensions((0, -1, 0), (2, 3, 4)) == [2, 4, 4]


def test_normalization_scale_maps_largest_dimension_to_target():
    dims = addon._bounds_dimensions((0, -1, 0), (2, 3, 4))  # -> [2, 4, 4]
    scale = addon._normalization_scale(max(dims), 2.0)
    assert scale == 0.5
    assert math.isclose(max(d * scale for d in dims), 2.0)


def test_normalization_scale_non_positive_returns_one():
    # Degenerate models (zero/negative max dimension) must not divide by zero.
    assert addon._normalization_scale(0, 5.0) == 1.0
    assert addon._normalization_scale(-3, 5.0) == 1.0


def test_end_to_end_normalization_preserves_aspect_ratio():
    # 8 corners of a 10 x 4 x 2 box offset from the origin.
    box = [
        (5, 2, 1), (5, 2, 3), (5, 6, 1), (5, 6, 3),
        (15, 2, 1), (15, 2, 3), (15, 6, 1), (15, 6, 3),
    ]
    mn, mx = addon._combine_world_bounds(box)
    dims = addon._bounds_dimensions(mn, mx)
    assert dims == [10, 4, 2]

    target = 1.0
    scale = addon._normalization_scale(max(dims), target)
    scaled = [d * scale for d in dims]

    assert math.isclose(max(scaled), target)
    assert math.isclose(scaled[0] / scaled[1], dims[0] / dims[1])
    assert math.isclose(scaled[1] / scaled[2], dims[1] / dims[2])
