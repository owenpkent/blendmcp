# Making BlenderMCP work better with Claude

This note captures a set of improvements to how Claude drives Blender through the
MCP server, what shipped on the `improve-claude-integration` branch, and what is
worth doing next.

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
  instance, discovered instances, and a `hint` when nothing is found). We could
  add `get_blender_status()` that reports connection state, which integrations
  are enabled, and a hint, instead of leaving connection debugging to the user.

- **Reconnect-once-and-retry.** On a transport error, uemcp closes the
  connection, reconnects, and retries the command once, so an editor restart
  mid-session is invisible. Our `send_command` invalidates the socket on error
  but makes the *next* call reconnect rather than transparently retrying the
  failed one. A single in-place retry would smooth over Blender restarts.

- **Sentinel-framed results with tracebacks.** uemcp wraps every host-side
  snippet in a harness that catches exceptions and prints
  `__UEMCP_RESULT__{json}` to the log, then parses that line back out, so it gets
  both structured results and the full Python traceback. Our `execute_code`
  returns only captured stdout. Adopting a sentinel + traceback would make
  failures in generated code far easier for Claude to diagnose. This pairs well
  with the "structured errors" item above.

- **Centralized env config with safe defaults.** uemcp has a config dataclass
  with a `from_env()` that type-converts each setting and falls back to the
  default on a malformed value instead of crashing. We read `BLENDER_HOST` /
  `BLENDER_PORT` inline; a small config object would centralize this and tolerate
  bad input.

- **Batch edits.** `ue_batch_edit` selects many objects and applies several
  operations in one round trip, returning per-item `{ok, error}` results. For
  "make all the chairs red" style requests this avoids N socket round trips. A
  `batch_edit` tool over our structured handlers would cut latency for bulk
  changes.

- **Compile-check tests for generated code.** uemcp unit tests every snippet
  builder by `compile()`-ing the generated source, catching syntax errors in CI
  without the host app. If we ever extract reusable code templates, the same
  cheap test applies.

- **Screenshot file-stability polling.** uemcp waits for the screenshot file to
  appear and for its size to stop changing before reading it. Our capture reads
  immediately; polling for stability would make screenshots more reliable,
  especially the first (cold) capture of a session.

Things we already do that uemcp does not: anonymous telemetry, an async lifespan,
exposing the screenshot path as an MCP-style image return, and more generation
backends (Hyper3D Rodin, Hunyuan3D). The highest-value, lowest-effort ports are
the **status tool**, **reconnect-once-and-retry**, and **sentinel + traceback
error reporting**.
