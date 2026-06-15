# Changelog

All notable changes to blendmcp are recorded here. blendmcp is a telemetry-free
fork of [blender-mcp](https://github.com/ahujasid/blender-mcp); the entries below
cover the fork's own releases. Versions are published on
[PyPI](https://pypi.org/project/blendmcp/).

## 1.4.2

- Renamed the Python import module to `blendmcp` (`import blendmcp`). The project
  is now uniformly `blendmcp` / BlendMCP across the PyPI package, the CLI command,
  the GitHub repo, the import module, and the Blender add-on.
- `blendmcp install-addon` now removes the older `mcpblender_addon.py` (shipped in
  1.4.1) when it installs, so upgrading does not leave two add-ons enabled.
- No changes to tool behavior.

## 1.4.1

- Renamed the user-facing Blender add-on and MCP server to **BlendMCP** to match
  the `blendmcp` package and command.
- Documentation refresh: PyPI/Python/license/CI badges, a quick start, and
  troubleshooting that points at `get_blender_status` first.
- No changes to tool behavior.

## 1.4.0

First release of the fork on PyPI.

- Structured editing tools: `add_primitive`, `modify_object`, `set_material`,
  `duplicate_object`, and `delete_object`. Each returns the affected object's
  world bounding box and dimensions so the result is confirmed in one step.
- `batch_edit` applies many editing operations in a single round trip, returning
  per-operation results.
- `get_blender_status` reports connection state, enabled integrations, and a
  server/add-on version handshake that warns when the add-on is out of date.
- The connection reconnects and retries once after a dropped socket.
- `execute_blender_code` can return a viewport screenshot (`return_screenshot`)
  and surfaces the full Python traceback when the code fails.
- The add-on ships inside the package and installs with `blendmcp install-addon`,
  keeping it on the same version as the server.
- Removed all telemetry/data-collection code; the fork sends no usage data.

Inherited from the original blender-mcp: viewport screenshots, 3D model
generation with Hunyuan3D and Hyper3D Rodin, Sketchfab search and download, Poly
Haven assets (models, textures, HDRIs), and running the MCP server on a remote
host.
