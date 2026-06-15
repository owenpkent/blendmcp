# Security Policy

## Supported versions

BlendMCP is distributed as a single package with no long-term support branches.
Only the latest released version on PyPI receives security fixes.

| Version | Supported |
| ------- | --------- |
| latest  | yes       |
| older   | no        |

## Reporting a vulnerability

Please report suspected vulnerabilities privately so a fix can be prepared
before public disclosure. Do not open a public issue for security reports.

Two ways to report:

1. GitHub private vulnerability reporting: open the repository's "Security" tab
   and choose "Report a vulnerability".
2. Email: Owenpkent@gmail.com

Please include enough detail to reproduce the issue: affected version, the
component (the MCP server, the Blender add-on, or a dependency), and a proof of
concept if you have one.

## What to expect

- An acknowledgement of your report, typically within a few days.
- An assessment of severity and the affected components.
- A fix released to PyPI once validated, with credit to the reporter if desired.

## Scope notes

- The MCP server runs over stdio by default and connects to a local Blender
  add-on listening on `localhost:9876`. It is intended to run on a trusted
  local machine, not exposed to untrusted networks.
- The `execute_blender_code` tool runs arbitrary Python inside Blender by
  design. Treat any client connected to the server as fully trusted.
