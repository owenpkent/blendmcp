"""Tests for the pure helpers in ``blender_mcp.server``.

These cover the color normalization used by the ``set_material`` tool and the
bounding-box ratio processing used by the Hyper3D generation tools. Neither
helper needs a Blender connection, so they can be exercised directly. Telemetry
is disabled via environment variable to keep the import side-effect-free.
"""
import os

os.environ.setdefault("DISABLE_TELEMETRY", "1")

import pytest

from blender_mcp.server import _normalize_rgba, _process_bbox


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
