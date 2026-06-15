

# MCPBlender - Blender Model Context Protocol Integration

MCPBlender connects Blender to Claude AI through the Model Context Protocol (MCP), allowing Claude to directly interact with and control Blender. This integration enables prompt assisted 3D modeling, scene creation, and manipulation.

**We have no official website. Any website you see online is unofficial and has no affiliation with this project. Use them at your own risk.**

[Full tutorial](https://www.youtube.com/watch?v=lCyQ717DuzQ)

### Join the Community

Give feedback, get inspired, and build on top of the MCP: [Discord](https://discord.gg/z5apgR8TFU)

### Supporters

[CodeRabbit](https://www.coderabbit.ai/)

[Satish Goda](https://github.com/satishgoda)

**All supporters:**

[Support this project](https://github.com/sponsors/ahujasid)

## Release notes (1.4.0)
- Added Hunyuan3D support

### Recent improvements
- Structured editing tools: `add_primitive`, `modify_object`, `set_material`, `duplicate_object`, and `delete_object`. These are more reliable than generating raw Python and they return the affected object's bounding box and dimensions so the result is confirmed in one step.
- `batch_edit` applies many editing operations in a single round trip, with per-operation results, for bulk changes.
- `get_blender_status` reports the connection state and which integrations are enabled. Call it first if a tool reports a connection problem.
- `execute_blender_code` now accepts `return_screenshot=True` to return a viewport image alongside the result, and surfaces the full Python traceback when the code fails so it can be corrected.
- The connection reconnects and retries once after a dropped socket, so restarting Blender mid-session no longer breaks the next call.
- The addon ships inside the package, so `blendmcp install-addon` keeps it on the same version as the server (a version handshake warns when it drifts).
- Removed the telemetry/data-collection code entirely; this fork sends no usage data.
- See `docs/claude-integration-improvements.md` for the rationale and the full list of changes.


### Previously added features:
- View screenshots for Blender viewport to better understand the scene
- Search and download Sketchfab models
- Support for Poly Haven assets through their API
- Support to generate 3D models using Hyper3D Rodin
- Run the MCP server on a remote host

### Installing a new version (existing users)
- For newcomers, you can go straight to Installation. For existing users, see the points below
- The addon now ships inside the `blendmcp` package, so the server and addon update together. If you installed the server as a uv tool, update both with:
  ```bash
  uv tool upgrade blendmcp
  blendmcp install-addon
  ```
  Then restart Blender. `blendmcp install-addon --list` shows detected Blender versions; `--all` installs into every one, and `--blender-version 4.2` targets one.
- Prefer manual? Download the latest `src/mcpblender/addon.py` and replace the older one in Blender.
- If your MCP client caches the server, remove and re-add it (or restart the client) so it picks up the new version.
- `get_blender_status` reports the server and addon versions and warns when the addon is out of date.


## Features

- **Two-way communication**: Connect Claude AI to Blender through a socket-based server
- **Structured editing tools**: Add primitives, transform objects, set materials, duplicate, and delete through dedicated tools that return the affected object's bounding box and dimensions for confirmation
- **Object manipulation**: Create, modify, and delete 3D objects in Blender
- **Material control**: Apply and modify materials and colors
- **Scene inspection**: Get detailed information about the current Blender scene
- **Visual feedback**: Capture viewport screenshots, including alongside `execute_blender_code` results
- **Code execution**: Run arbitrary Python code in Blender from Claude

## Components

The system consists of two main components:

1. **Blender Addon (`addon.py`)**: A Blender addon that creates a socket server within Blender to receive and execute commands
2. **MCP Server (`src/mcpblender/server.py`)**: A Python server that implements the Model Context Protocol and connects to the Blender addon

## Installation


### Prerequisites

- Blender 3.0 or newer
- Python 3.10 or newer
- uv package manager: 

**If you're on Mac, please install uv as**
```bash
brew install uv
```
**On Windows**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex" 
```
and then add uv to the user path in Windows (you may need to restart Claude Desktop after):
```powershell
$localBin = "$env:USERPROFILE\.local\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$userPath;$localBin", "User")
```

Otherwise installation instructions are on their website: [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

**⚠️ Do not proceed before installing UV**

### Environment Variables

The following environment variables can be used to configure the Blender connection:

- `BLENDER_HOST`: Host address for Blender socket server (default: "localhost")
- `BLENDER_PORT`: Port number for Blender socket server (default: 9876)

Example:
```bash
export BLENDER_HOST='host.docker.internal'
export BLENDER_PORT=9876
```

### Claude for Desktop Integration

[Watch the setup instruction video](https://www.youtube.com/watch?v=neoK_WMq92g) (Assuming you have already installed uv)

Go to Claude > Settings > Developer > Edit Config > claude_desktop_config.json to include the following:

```json
{
    "mcpServers": {
        "blendmcp": {
            "command": "uvx",
            "args": [
                "blendmcp"
            ]
        }
    }
}
```

### Cursor integration

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=blendmcp&config=eyJjb21tYW5kIjoidXZ4IGJsZW5kbWNwIn0%3D)

For Mac users, go to Settings > MCP and paste the following 

- To use as a global server, use "add new global MCP server" button and paste
- To use as a project specific server, create `.cursor/mcp.json` in the root of the project and paste


```json
{
    "mcpServers": {
        "blendmcp": {
            "command": "uvx",
            "args": [
                "blendmcp"
            ]
        }
    }
}
```

For Windows users, go to Settings > MCP > Add Server, add a new server with the following settings:

```json
{
    "mcpServers": {
        "blendmcp": {
            "command": "cmd",
            "args": [
                "/c",
                "uvx",
                "blendmcp"
            ]
        }
    }
}
```

[Cursor setup video](https://www.youtube.com/watch?v=wgWsJshecac)

**⚠️ Only run one instance of the MCP server (either on Cursor or Claude Desktop), not both**

### Visual Studio Code Integration

_Prerequisites_: Make sure you have [Visual Studio Code](https://code.visualstudio.com/) installed before proceeding.

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_blendmcp_server-0098FF?style=flat-square&logo=visualstudiocode&logoColor=ffffff)](vscode:mcp/install?%7B%22name%22%3A%22blendmcp%22%2C%22type%22%3A%22stdio%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22blendmcp%22%5D%7D)

### Installing the Blender Addon

The addon ships inside the `blendmcp` package, so you can install it with one
command instead of downloading a file. After installing the server as a uv tool:

```bash
uv tool install blendmcp   # if you have not already
blendmcp install-addon
```

This copies the addon into your Blender add-ons folder (use `--list` to see
detected Blender versions, `--all` for every version, or `--blender-version 4.2`
for a specific one). Then open Blender, go to Edit > Preferences > Add-ons, and
enable "Interface: Blender MCP". This keeps the addon on the same version as the
server, which matters because newer tools require the matching addon.

**Manual install (alternative):**

1. Download `src/mcpblender/addon.py` from this repo
2. Open Blender
3. Go to Edit > Preferences > Add-ons
4. Click "Install..." and select the `addon.py` file
5. Enable the addon by checking the box next to "Interface: Blender MCP"


## Usage

### Starting the Connection
![MCPBlender in the sidebar](assets/addon-instructions.png)

1. In Blender, go to the 3D View sidebar (press N if not visible)
2. Find the "MCPBlender" tab
3. Turn on the Poly Haven checkbox if you want assets from their API (optional)
4. Click "Connect to Claude"
5. Make sure the MCP server is running in your terminal

### Using with Claude

Once the config file has been set on Claude, and the addon is running on Blender, you will see a hammer icon with tools for the Blender MCP.

![MCPBlender in the sidebar](assets/hammer-icon.png)

#### Capabilities

- Get scene and object information 
- Add primitives and create, delete, duplicate and modify shapes through dedicated tools that confirm the result
- Apply or create materials for objects
- Execute any Python code in Blender (optionally returning a viewport screenshot)
- Download the right models, assets and HDRIs through [Poly Haven](https://polyhaven.com/)
- AI generated 3D models through [Hyper3D Rodin](https://hyper3d.ai/)


### Example Commands

Here are some examples of what you can ask Claude to do:

- "Create a low poly scene in a dungeon, with a dragon guarding a pot of gold" [Demo](https://www.youtube.com/watch?v=DqgKuLYUv00)
- "Create a beach vibe using HDRIs, textures, and models like rocks and vegetation from Poly Haven" [Demo](https://www.youtube.com/watch?v=I29rn92gkC4)
- Give a reference image, and create a Blender scene out of it [Demo](https://www.youtube.com/watch?v=FDRb03XPiRo)
- "Generate a 3D model of a garden gnome through Hyper3D"
- "Get information about the current scene, and make a threejs sketch from it" [Demo](https://www.youtube.com/watch?v=jxbNI5L7AH8)
- "Make this car red and metallic" 
- "Create a sphere and place it above the cube"
- "Make the lighting like a studio"
- "Point the camera at the scene, and make it isometric"

## Hyper3D integration

Hyper3D's free trial key allows you to generate a limited number of models per day. If the daily limit is reached, you can wait for the next day's reset or obtain your own key from hyper3d.ai and fal.ai.

## Troubleshooting

- **Connection issues**: Make sure the Blender addon server is running, and the MCP server is configured on Claude, DO NOT run the uvx command in the terminal. Sometimes, the first command won't go through but after that it starts working.
- **Timeout errors**: Try simplifying your requests or breaking them into smaller steps
- **Poly Haven integration**: Claude is sometimes erratic with its behaviour
- **Have you tried turning it off and on again?**: If you're still having connection errors, try restarting both Claude and the Blender server


## Technical Details

### Communication Protocol

The system uses a simple JSON-based protocol over TCP sockets:

- **Commands** are sent as JSON objects with a `type` and optional `params`
- **Responses** are JSON objects with a `status` and `result` or `message`

## Limitations & Security Considerations

- The `execute_blender_code` tool allows running arbitrary Python code in Blender, which can be powerful but potentially dangerous. Use with caution in production environments. ALWAYS save your work before using it.
- Poly Haven requires downloading models, textures, and HDRI images. If you do not want to use it, please turn it off in the checkbox in Blender. 
- Complex operations might need to be broken down into smaller steps


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development

Tests live in `tests/` and run outside Blender. Because `addon.py` imports `bpy`
(only available inside Blender), `tests/conftest.py` installs lightweight
stand-ins for `bpy`, `mathutils`, and `requests` so the addon's pure helper
functions can be imported and tested directly.

Install the dev dependencies and run the suite with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
uv run pytest
```

The current tests cover the geometry helpers used for Sketchfab model
size normalization (`_combine_world_bounds`, `_bounds_dimensions`,
`_normalization_scale` in `addon.py`) and the pure helpers and connection
behavior in `src/mcpblender/server.py` (color normalization, environment config
loading, reconnect-once-and-retry, structured code-execution errors, and batch
color normalization).

## Credits and disclaimer

This is a third-party integration and not made by Blender. MCPBlender is a fork of
[blender-mcp](https://github.com/ahujasid/blender-mcp) by [Siddharth Ahuja](https://x.com/sidahuj),
maintained by [Owen Kent](https://github.com/owenpkent). It keeps the original MIT
license and copyright. Unlike upstream, this fork collects no telemetry.
