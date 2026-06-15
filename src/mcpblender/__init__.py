"""Blender integration through the Model Context Protocol."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("blendmcp")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "unknown"

# Expose key classes and functions for easier imports
from .server import BlenderConnection, get_blender_connection
