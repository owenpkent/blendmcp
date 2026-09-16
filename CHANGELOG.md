# Changelog

All notable changes to blendmcp are recorded here. blendmcp is a telemetry-free
fork of [blender-mcp](https://github.com/ahujasid/blender-mcp); the entries below
cover the fork's own releases. Versions are published on
[PyPI](https://pypi.org/project/blendmcp/).

## 1.4.5

Poly Haven textures now use every map they ship.

- Fixed the map-name matching in `set_texture`. Map types are parsed from the
  image filename, and Poly Haven capitalizes several of them (`Diffuse`, `AO`,
  `Rough`, `Displacement`), while the wiring pass compared them against
  lower-case names. Three maps were silently dropped on every Poly Haven
  texture that ships an ARM map: ambient occlusion was never multiplied into
  the base color, and a dedicated roughness or metallic map lost to the ARM
  channel that is only used when no dedicated map exists. Map names are now
  normalized when they are parsed.
- Fixed the base-color map loading as `Non-Color` in
  `download_polyhaven_asset`, the same case-sensitivity bug in the colorspace
  assignment, which left the material built at download time washed out.
- A dedicated AO map now takes precedence over the ARM red channel, matching
  how dedicated roughness and metallic maps already behave. Applying a texture
  that ships both no longer builds two multiply nodes where the second hides
  the first.
- `set_texture` no longer wires maps twice. Its first pass created the image
  nodes and linked them, then the second pass linked them again, leaving a
  duplicate Normal Map node and a duplicate Displacement node shadowing the
  connected ones. The first pass now only creates nodes.
- Added material-graph tests using Poly Haven's own capitalization and a
  texture set with both ARM and dedicated AO maps. The existing cases all used
  lower-case names, so they never exercised the paths that were broken. All 105
  tests pass; CI passes on Python 3.10, 3.11, and 3.12.
- Verified against Blender 5.2.2 LTS: applying `brick_wall_02` at 1k wires the
  AO multiply into base color, the dedicated `Rough` map into Roughness, ARM
  blue into Metallic, and one normal and one displacement node.

## 1.4.4

[GitHub release](https://github.com/owenpkent/blendmcp/releases/tag/v1.4.4) ·
[PyPI](https://pypi.org/project/blendmcp/1.4.4/)

Blender 5 support, and a fix for fresh installs.

- Fixed `set_texture` on Blender 5.x. The add-on built its ARM (ambient
  occlusion / roughness / metallic) channel split with `ShaderNodeSeparateRGB`,
  which Blender removed in 5.0, so applying any Poly Haven texture that ships an
  ARM map failed with "Node type ShaderNodeSeparateRGB undefined". It now uses
  `ShaderNodeSeparateColor` and falls back to the old node on Blender 3.0–3.2.
- Fixed the ambient-occlusion mix on Blender 5.x: the `MixRGB` factor socket was
  renamed from `Fac` to `Factor`, so it is now addressed by index.
- Constrained the `mcp` dependency to `<2`. mcp 2.0 renamed `FastMCP` to
  `MCPServer`; the server targets the v1 API, so a fresh `uvx blendmcp` resolved
  mcp 2.x and crashed on import with `No module named 'mcp.server.fastmcp'`.
- Verified against Blender 4.5.9 LTS and 5.2.2: add-on registration, the scene
  and object tools, primitives, materials, batch edits, viewport screenshots,
  and the Poly Haven HDRI, texture, and model pipelines.
- Added behavioral material-graph tests across simulated Blender 3.x–5.x node
  APIs for ARM channels, dedicated roughness/metallic map precedence, AO mixing,
  and ARM without a base-color map. The dependency test now parses the MCP
  requirement and checks allowed and excluded versions. All 99 tests pass;
  CI passes on Python 3.10, 3.11, and 3.12.

## 1.4.3

Security and dependency maintenance. No changes to tool behavior.

- Updated dependencies to current releases, picking up upstream security fixes
  (`mcp`, `starlette`, `h11`, `idna`, `pygments`, `python-dotenv`). The server
  uses the stdio transport, so the HTTP-transport advisories did not apply, but
  the versions are refreshed regardless.
- Added request timeouts to every outbound HTTP call in the add-on (Poly Haven,
  Sketchfab, Hyper3D, Hunyuan3D) so a stalled download no longer hangs Blender.
- Hardened the GitHub Actions workflows: pinned actions to commit SHAs, dropped
  persisted credentials on checkout, and scoped `GITHUB_TOKEN` to least
  privilege.
- Added a security policy (`SECURITY.md`) and Dependabot configuration for
  weekly dependency and action updates.

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
