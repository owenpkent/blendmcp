# Making BlendMCP work better with Claude

This note captures a set of improvements to how Claude drives Blender through the
MCP server, what shipped on the `improve-claude-integration` branch, and what is
worth doing next.

> Note: this project was later forked and rebranded from `blender-mcp` to
> `blendmcp`, and the telemetry described in section 1 was **removed entirely**
> in the fork. That section is kept as a record of the original finding; the fork
> ships no telemetry. See "Forking to blendmcp" at the end.

## Why these changes

The original tool surface was heavy on asset integrations (PolyHaven, Sketchfab,
Hyper3D, Hunyuan3D) but thin on core editing. Every basic operation (add a cube,
move it, color it) went through `execute_blender_code`, where Claude writes raw
`bpy` and gets back only captured stdout. That has two costs:

1. **No feedback loop.** Claude acts, then has to separately decide to call
   `get_scene_info` or `get_viewport_screenshot` to find out what happened. For a
   visual tool that is the single biggest limit on success rate.
2. **Fragile codegen.** The `bpy` API is large and version-sensitive, so raw code
   is exactly where Claude hallucinates calls and you get the timeout/retry loops
   that the README lists as the top complaint.

## What shipped

### 1. Telemetry actually fires now (headline bug)

`@telemetry_tool(...)` was applied **outside** `@mcp.tool()`. Because
`mcp.tool()` registers the bare function and returns it unchanged, the telemetry
wrapper was bound to the module name but never placed in the call path. Every
decorated tool ran without recording usage, so the "Telemetry for tools executed"
feature was effectively dead.

Fix: swap the order so `@mcp.tool()` is outermost and `@telemetry_tool(...)` is
inner. `inspect.signature` follows `functools.wraps`'s `__wrapped__`, so the tool
schemas are unchanged (verified empirically). Consent gating is unchanged: events
still flow only through `TelemetryCollector` with its `config.enabled` and
`DISABLE_TELEMETRY` checks, the same path startup events already used.

Also in this pass:
- `get_sketchfab_model_preview` was decorated with the name
  `"download_sketchfab_model"`, so preview calls were mislabeled. Corrected.
- `download_sketchfab_model` and the four Hunyuan tools had no telemetry at all.
  Added.

### 2. `input_image_urls` bug in `generate_hyper3d_model_via_images`

The URL branch iterated `input_image_paths` (which is `None` there), raising
`TypeError` before any request. It also used `urlparse(i)` as a truthiness check,
which is always true. Now it iterates `input_image_urls` and validates that each
URL has a scheme and a netloc.

### 3. Structured editing tools with a built-in feedback loop

New MCP tools (and matching `addon.py` handlers) for the operations Claude used to
do via raw `bpy`:

| Tool | Purpose |
| --- | --- |
| `add_primitive` | cube/sphere/cylinder/cone/plane/torus/circle/monkey |
| `modify_object` | move, rotate, scale, show/hide |
| `set_material` | Principled BSDF base color, metallic, roughness |
| `duplicate_object` | reuse an asset without regenerating it |
| `delete_object` | remove an object |

Each editing handler returns a compact **object summary** (`name`, `location`,
`rotation`, `scale`, `materials`, and for meshes the `world_bounding_box` and
`dimensions`). That summary *is* the scene delta, so Claude gets confirmation of
the result without a follow-up query. This directly serves the strategy prompt's
repeated instruction to "always check the world_bounding_box."

### 4. Screenshot feedback loop on `execute_blender_code`

`execute_blender_code` gained `return_screenshot: bool = False`. When set, it
captures the viewport after running the code and returns `[text, Image]` in the
same response, so Claude can see the effect of custom code without spending a
turn. Screenshot capture was refactored into `_capture_viewport_image` so the
dedicated screenshot tool and this path stay in sync. A screenshot failure
degrades gracefully to text plus a note.

### 5. Guidance folded into docstrings and the strategy prompt

The `asset_creation_strategy` prompt and the relevant docstrings now point Claude
at the dedicated editing tools before raw scripting, and mention
`return_screenshot`. Docstrings always reach the model, whereas the prompt only
applies if the user selects it, so the important steering lives in both places.

### 6. Tests

`tests/test_server_helpers.py` covers the new pure helper `_normalize_rgba` and
the previously untested `_process_bbox`. Full suite: `uv run pytest`.

## Testing notes / caveats

- The `addon.py` handlers call `bpy` and can only be fully verified inside
  Blender. They were written to match the existing handler style and are
  defensive about missing objects and unsupported types, but they should be smoke
  tested in a real Blender session (add each primitive type, modify, set a
  material, duplicate, delete) before release.
- `_object_summary` reuses the existing `_get_aabb`, which raises on non-mesh
  objects; the summary only adds bounding-box/dimension fields for meshes.

## Worth doing next (not in this branch)

- **Self-completing generation.** Hyper3D and Hunyuan force Claude to loop
  generate -> poll -> import across turns. A single `generate_and_import` that
  polls server-side would collapse three brittle round-trips into one.
- **Structured errors.** Tools return ad-hoc `"Error: ..."` strings. A small
  `{status, message, hint, retryable}` shape would let Claude distinguish a
  transient timeout (retry/simplify) from an auth failure (stop).
- **Drop the per-call PolyHaven ping.** `get_blender_connection()` sends a
  `get_polyhaven_status` command on every tool call as a health check, adding a
  socket round-trip to every operation. Cache it with a TTL or use a cheap ping.
- **Expose the scene as an MCP resource** so Claude can read current state without
  spending a tool call.
- **Undo checkpoints.** Pushing an undo step (or auto-saving) before
  `execute_blender_code` would let Claude recover from a bad edit and reduce the
  risk of the arbitrary-code path.

## Lessons from the uemcp sibling project

`uemcp` (an MCP server for Unreal Engine that drives the editor over Unreal's
built-in Python remote execution) solves the same shape of problem and has
several patterns worth porting. It independently arrived at the same two big
ideas we just added here (dedicated structured tools that return state, and a
"change -> screenshot -> verify" loop), which is a good signal those were the
right calls. What it does that we do not yet:

- **A health/status tool.** `ue_status` is the documented "call this first if a
  tool fails" entry point. It returns a diagnostic object (connected, which
  instance, discovered instances, and a `hint` when nothing is found).

  **Implemented.** `get_blender_status()` reports the configured host/port,
  whether the connection is live, which integrations are enabled, and a `hint`
  for fixing a failed connection. Its docstring tells the model to call it first
  when another tool reports a connection problem.

- **Reconnect-once-and-retry.** On a transport error, uemcp closes the
  connection, reconnects, and retries the command once, so an editor restart
  mid-session is invisible.

  **Implemented.** `send_command` now reconnects and retries once on a
  connection-level error. Timeouts are deliberately *not* retried, because
  Blender may still be executing the original command and a retry could
  double-apply a mutation.

- **Sentinel-framed results with tracebacks.** uemcp wraps every host-side
  snippet in a harness that catches exceptions and returns both structured
  results and the full Python traceback.

  **Implemented (without the literal sentinel).** Our socket protocol already
  returns structured JSON, so the win was the traceback: `execute_code` now
  returns `{executed, result, error, traceback}` instead of raising, and
  `execute_blender_code` surfaces the error and traceback to the model so it can
  correct the code. This also covers the "structured errors" item above for the
  arbitrary-code path.

- **Centralized env config with safe defaults.** uemcp has a config dataclass
  with a `from_env()` that type-converts each setting and falls back to the
  default on a malformed value instead of crashing.

  **Implemented.** `BlendMCPConfig.from_env()` loads `BLENDER_HOST` /
  `BLENDER_PORT`, logging a warning and keeping the default when the port is
  malformed instead of crashing on `int(...)`.

- **Batch edits.** `ue_batch_edit` applies several operations in one round trip,
  returning per-item `{ok, error}` results.

  **Implemented.** `batch_edit(operations)` runs a list of `add_primitive` /
  `modify_object` / `set_material` / `duplicate_object` / `delete_object` ops in
  order and returns `{total, applied, failed, results}` with per-op outcomes. A
  failed op does not stop the batch. `set_material` colors are normalized before
  sending.

- **Screenshot file-stability polling.** uemcp waits for the screenshot file to
  appear and stop changing in size before reading it.

  **Implemented.** `_wait_for_stable_file` waits for the capture file to exist
  and its size to settle before reading. Blender's screenshot op is synchronous,
  so this is a cheap safety margin rather than a strict need, but it removes a
  race on slow disks and cold captures.

- **Compile-check tests for generated code.** uemcp unit tests every snippet
  builder by `compile()`-ing the generated source.

  **Not applicable.** blendmcp sends structured commands rather than generated
  Python templates, so there is no snippet source to compile-check. The
  equivalent investment here is the expanded `tests/test_server_helpers.py`
  coverage (config loading, retry/no-retry, traceback surfacing, batch color
  normalization, file-stability wait).

Things we already do that uemcp does not: anonymous telemetry, an async lifespan,
exposing the screenshot path as an MCP-style image return, and more generation
backends (Hyper3D Rodin, Hunyuan3D).

Still open from the broader list above: self-completing generation, a fully
structured error shape across *all* tools (the traceback work covers the
arbitrary-code path), dropping the per-call PolyHaven ping in
`get_blender_connection`, exposing the scene as an MCP resource, and undo
checkpoints before `execute_blender_code`.

## Easy install and update

The server was already on PyPI (`uvx blendmcp`), but the addon was not: it
lived at the repo root, was installed by hand, and updated by re-downloading the
file. Nothing tied its version to the server's, and in fact the addon
(`bl_info` 1.2), the package (`pyproject` 1.4.0), and `__init__.__version__`
(0.1.0) had all drifted apart. A stale addon silently breaks newer tools, since
the structured handlers, `batch_edit`, and the traceback-returning `execute_code`
all live in the addon.

What changed:

- **The addon ships inside the package.** `addon.py` moved to
  `src/blendmcp/addon.py`, so it is part of the wheel. One source of truth.
- **`blendmcp install-addon`** locates the Blender add-ons directory for the
  OS and copies the bundled addon in (`--list`, `--all`, `--blender-version`,
  `--uninstall`). It is a subcommand of the existing entry point, so the no-arg
  invocation MCP clients use still launches the server. Update flow:
  `uv tool upgrade blendmcp && blendmcp install-addon`.
- **Versions are single-sourced.** `__init__.__version__` now reads the installed
  package version, the addon `bl_info` is set to match `pyproject`, and a test
  (`test_addon_version_matches_package`) fails if they drift again.
- **Version handshake.** The addon answers `get_addon_version`, and
  `get_blender_status` reports `server_version`, `addon_version`, and a `hint`
  telling the user to run `install-addon` when the addon is older than the server
  (or too old to report its version at all).

## Forking to blendmcp

Rather than contribute upstream, this became a standalone fork on the maintainer's
own PyPI and GitHub. Everything uses one name: **`blendmcp`** is the PyPI
distribution, the CLI command (`uvx blendmcp`), the `import blendmcp` module, and
the GitHub repo (`owenpkent/blendmcp`); the Blender add-on appears as **BlendMCP**.

Two detours along the way are worth recording:

- The project was first rebranded to `mcpblender`, but PyPI rejected that as a
  *distribution* name (too similar to the existing `blender-mcp` / `mcp-blender`).
  So it was published as `blendmcp` while the import module stayed `mcpblender`
  for a release, then the module was renamed to `blendmcp` too.
- The GitHub repo was renamed `mcpblender` -> `blendmcp`. Because the PyPI Trusted
  Publisher matches on the current repo name, its Repository field had to be
  updated to `blendmcp` or releases would stop publishing.

The version handshake reads the distribution metadata, so `_server_version()` and
`__init__.__version__` look up `blendmcp`.

What the rebrand changed:

- **Rename.** The import package (`blender_mcp` -> `blendmcp`), the CLI command
  and PyPI distribution (`blender-mcp` -> `blendmcp`), and the Blender addon's
  display name and sidebar tab (`Blender MCP` / `BlenderMCP` -> `BlendMCP`).
  Internal Blender identifiers (`blendermcp_*` scene properties, `BLENDERMCP_*`
  operator classes, `bl_idname`s) were left as-is because they are not
  user-facing and renaming them is untestable churn.
- **Telemetry removed entirely.** `telemetry.py`, `telemetry_decorator.py`, the
  `@telemetry_tool` decorators, the addon's consent preference and Terms operator,
  and the `supabase`/`tomli` dependencies are all gone. The fork sends no data.
  (This supersedes section 1 above.)
- **Attribution preserved.** The MIT license keeps Siddharth Ahuja's original
  copyright and adds the fork's; the addon header and README credit upstream.
- **Metadata updated.** `pyproject` author/URLs point at the fork; the addon
  `bl_info` author is the fork maintainer.

The directory installer and the version handshake are unchanged by the rename;
they work under any package name.
