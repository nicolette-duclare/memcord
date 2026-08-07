# Installation & Configuration

This guide covers the complete installation and configuration process for the MemCord MCP Server.

## Prerequisites

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

## Installation

### Install with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/ukkit/memcord.git
cd memcord

# Install with uv (core deps including sumy)
uv pip install -e .
```

### Install with pip

```bash
# Clone the repository
git clone https://github.com/ukkit/memcord.git
cd memcord

# Install dependencies
pip install -e .
```

### Optional Summarizer Backends

The default summarizer is `sumy` (graph-based, zero model files, included in core deps). Two heavier backends are available as optional extras:

```bash
# Semantic backend — sentence-transformers + MMR (~80MB one-time download)
uv pip install -e ".[semantic]"
pip install -e ".[semantic]"

# Transformers backend — HuggingFace BART abstractive summarizer (~400MB one-time download)
uv pip install -e ".[transformers]"
pip install -e ".[transformers]"
```

After installing, configure a slot to use the new backend:
```
memcord_configure action="set" key="summarizer_backend" value="semantic"
memcord_configure action="set" key="summarizer_backend" value="transformers"
```

## Configuration

### OpenClaw

**Step 1 — Install the skill from ClawHub:**

```bash
openclaw skills install memcord --force
```

**Step 2 — Add the MCP server config manually** to `~/.openclaw/openclaw.json`:

```json
{
  "mcp": {
    "servers": {
      "memcord": {
        "command": "uvx",
        "args": ["memcord"],
        "toolFilter": {
          "include": ["memcord_auto_save", "memcord_read"]
        }
      }
    }
  }
}
```

To use a named slot instead of the default `"default"` slot, add an `"env"` field:

```json
{
  "mcp": {
    "servers": {
      "memcord": {
        "command": "uvx",
        "args": ["memcord"],
        "env": { "MEMCORD_DEFAULT_SLOT": "main" },
        "toolFilter": {
          "include": ["memcord_auto_save", "memcord_read"]
        }
      }
    }
  }
}
```

**Step 3 — Verify:**

```bash
openclaw mcp list
```

Memcord exposes two tools in OpenClaw: `memcord_auto_save` (write) and `memcord_read` (read). The `uvx memcord` command downloads memcord from PyPI on first run — no separate installation required.

### Claude Code CLI (Recommended) ⭐

`scripts/generate-config.py` (and the `install.sh`/`install.ps1` installers that call it)
register memcord with Claude Code automatically. By default it registers **globally**
(`~/.claude.json`), so memcord is available in every project without per-project setup.
Pass `--scope project` to instead write a project-level `.mcp.json` next to the memcord
checkout — useful for team sharing via version control. Re-running the installer to
update an existing checkout auto-detects and preserves whichever scope you're already
using.

```bash
# Global (default): available in every project
uv run python scripts/generate-config.py

# Project-level: shared with your team via .mcp.json in version control
uv run python scripts/generate-config.py --scope project
```

#### Project-Level Installation (Team Sharing)

```bash
# Navigate to the memcord project directory
cd /path/to/memcord

# Install the MCP server for this project
claude mcp install ./

# Or install from the current directory
claude mcp install .
```

#### Manual Claude Code Configuration

The installer's `--scope` flag (above) covers most cases. If you prefer manual configuration via the `claude` CLI directly, or need custom settings, run these from any directory — replace `/path/to/memcord` with the absolute path to your memcord installation:

**macOS / Linux:**
```bash
# Project-specific (shared with team via version control)
claude mcp add memcord uv --directory /path/to/memcord run memcord --scope project -e PYTHONPATH=/path/to/memcord/src -e MEMCORD_ENABLE_ADVANCED=false

# User-wide (available across all projects)
claude mcp add memcord uv --directory /path/to/memcord run memcord --scope user -e PYTHONPATH=/path/to/memcord/src -e MEMCORD_ENABLE_ADVANCED=false
```

**Windows (PowerShell):**

Windows requires `cmd /c` wrapper and `add-json` to avoid argument parsing issues:
```powershell
# Project-specific (shared with team via version control)
claude mcp add-json memcord '{"type":"stdio","command":"cmd","args":["/c","uv","--directory","C:\\path\\to\\memcord","run","memcord"],"env":{"PYTHONPATH":"C:\\path\\to\\memcord\\src","MEMCORD_ENABLE_ADVANCED":"false"}}' --scope project

# User-wide (available across all projects)
claude mcp add-json memcord '{"type":"stdio","command":"cmd","args":["/c","uv","--directory","C:\\path\\to\\memcord","run","memcord"],"env":{"PYTHONPATH":"C:\\path\\to\\memcord\\src","MEMCORD_ENABLE_ADVANCED":"false"}}' --scope user
```

#### Verification

Verify the server is configured correctly:
```bash
# List all configured MCP servers
claude mcp list

# Get detailed information about memcord
claude mcp get memcord

# Test the server startup
claude mcp test memcord
```

#### Advanced Tools

By default, the `.mcp.json` configuration enables all 23 tools (15 basic + 8 advanced). To use only basic tools, set:

```bash
# Disable advanced tools
claude mcp configure memcord -e MEMCORD_ENABLE_ADVANCED=false
```

#### Summarizer Backend (Optional)

Set `MEMCORD_SUMMARIZER` to override the per-slot summarizer config for all slots. Useful for Docker/CI where you want a fixed backend regardless of individual slot settings:

```bash
# Force sumy for all slots (default for new slots anyway)
claude mcp configure memcord -e MEMCORD_SUMMARIZER=sumy

# Force NLTK for all slots (backward-compatible, no extra deps)
claude mcp configure memcord -e MEMCORD_SUMMARIZER=nltk

# Force semantic backend (requires: pip install memcord[semantic])
claude mcp configure memcord -e MEMCORD_SUMMARIZER=semantic

# Force transformers backend (requires: pip install memcord[transformers])
claude mcp configure memcord -e MEMCORD_SUMMARIZER=transformers
```

When not set, each slot uses its own backend as configured via `memcord_configure`.

#### Storage Directory (Optional)

Set `MEMCORD_MEMORY_DIR` to change where memory slots are stored, e.g. to point at a synced Dropbox/OneDrive folder instead of the default `memory_slots/` next to the project. `MEMCORD_SHARED_DIR` does the same for shared memory exports:

```bash
claude mcp configure memcord -e MEMCORD_MEMORY_DIR=/Users/me/Dropbox/memcord-data
claude mcp configure memcord -e MEMCORD_SHARED_DIR=/Users/me/Dropbox/memcord-shared
```

When not set, memcord uses `memory_slots/` and `shared_memories/` relative to the working directory the MCP client launches it from.

#### Auto-Save Hooks (Optional)

Memcord can automatically save conversation progress when Claude Code compacts context:

```bash
uv run python scripts/generate-config.py --install-hooks
```

This installs agent hooks into `.claude/settings.json`:
- **PreCompact** — saves a summary before context compaction

> **Note:** `SessionEnd` with `type: "agent"` is not supported by Claude Code. Re-running `--install-hooks` will automatically remove any stale `SessionEnd` hook from a previous install.

**Verify installation:** Check `.claude/settings.json` for a `hooks.PreCompact` entry with a `"memcord:"` description.

**Remove hooks:** Edit `.claude/settings.json` and delete the memcord hook entry from the `PreCompact` array.

### Claude Desktop

MemCord offers two tool modes. Choose the configuration that fits your needs:

**Configuration Files**:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Basic Mode (Default - 15 Tools)
Essential memory management features:

```json
{
  "mcpServers": {
    "memcord": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/memcord",
        "run",
        "memcord"
      ],
      "env": {
        "PYTHONPATH": "/path/to/memcord/src"
      }
    }
  }
}
```

#### Advanced Mode (All 23 Tools)
Includes organization, import/export, and advanced features:

```json
{
  "mcpServers": {
    "memcord": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/memcord",
        "run",
        "memcord"
      ],
      "env": {
        "PYTHONPATH": "/path/to/memcord/src",
        "MEMCORD_ENABLE_ADVANCED": "true"
      }
    }
  }
}
```

**Note**: You can switch between modes anytime by changing the environment variable and restarting Claude Desktop.

### Other MCP Applications

The server can be started directly:

```bash
# Run the server
uv run memcord

# Or with Python
python -m memcord.server
```

## Custom Claude Code Commands

Memcord ships 17 ready-made slash commands in `.claude/commands/memcord-*.md`. This
directory is git-tracked, so anyone who clones the repo already has all 17 available at
**project scope** the moment their Claude Code cwd is the memcord checkout — no setup
needed there.

### Installing Commands Globally

To use the commands from *any* project directory (not just the memcord checkout),
install them into `~/.claude/commands/`:

```bash
uv run python scripts/generate-config.py --manage-commands   # interactive picker
uv run python scripts/generate-config.py --commands all      # non-interactive: install all
uv run python scripts/generate-config.py --commands none     # non-interactive: remove all
uv run python scripts/generate-config.py --commands memcord-save,memcord-read
```

Fresh `install.sh`/`install.ps1` runs prompt for this automatically at the end (skipped
when non-interactive, e.g. `curl | bash`, printing the manual command instead). Re-run
`--manage-commands` any time to add or remove commands — it's idempotent and diffs
against what's currently installed. Only memcord's own command files (exact filename
matches against the 17 shipped names) are ever added or removed; anything else already
in `~/.claude/commands/` is left alone. If you've hand-edited an installed command file
and later deselect it, memcord renames it to `<name>.md.bak` instead of deleting it.

### Available Commands

| Command | Description |
|---|---|
| `memcord-clear` | Save memory and clear context |
| `memcord-close` | Deactivate memory slot and end session |
| `memcord-import` | Import content from files/URLs |
| `memcord-init` | Initialize a project directory with a memory slot |
| `memcord-list` | List all memory slots |
| `memcord-merge` | Merge multiple memory slots with duplicate detection |
| `memcord-name` | Create or select a memory slot |
| `memcord-query` | Ask questions about your memories |
| `memcord-read` | Read from memory slot |
| `memcord-save` | Save current conversation to memory |
| `memcord-save-progress` | Auto-summarize and save conversation progress |
| `memcord-search` | Search across all memory slots |
| `memcord-select-entry` | Select specific memory entry by time or index |
| `memcord-tag` | Add, remove, or list tags for memory organization |
| `memcord-unbind` | Remove .memcord binding from a project directory |
| `memcord-use` | Activate an existing memory slot |
| `memcord-zero` | Activate zero mode - prevent memory saving |

### Usage

```
/memcord-save project_discussion
/memcord-read project_discussion
/memcord-list
/memcord-search API changes
/memcord-query "What decisions were made last week?"
```

## MCP File Resources

Memory slots are automatically available as MCP file resources:

- `memory://slot_name.md` - Markdown format
- `memory://slot_name.txt` - Plain text format
- `memory://slot_name.json` - JSON format

These resources update automatically when memory slots change and can be accessed by other MCP applications.

## Update Existing Installation

### Recommended: Re-run the installer

`install.sh` / `install.ps1` detect an existing installation and update it in place — pulling the latest changes (fast-forward only), reusing your existing virtual environment, upgrading dependencies, and regenerating MCP configs. Your `memory_slots/` data and generated config files are untouched. The Claude Code scope (`project` vs `user`) is auto-detected from whether a `.mcp.json` already exists in the checkout, so updating never silently switches an existing team-shared install to global scope.

Run this from the directory containing your `memcord` checkout (or from inside it):

**macOS / Linux:**
```bash
curl -fsSL https://github.com/ukkit/memcord/raw/main/install.sh | bash

# Pass --scope to override auto-detection:
curl -fsSL https://github.com/ukkit/memcord/raw/main/install.sh | bash -s -- --scope project
```

**Windows (PowerShell):**
```powershell
irm https://github.com/ukkit/memcord/raw/main/install.ps1 | iex

# Pass -Scope to override auto-detection:
& ([scriptblock]::Create((irm https://github.com/ukkit/memcord/raw/main/install.ps1))) -Scope project
```

If tracked files have local modifications, the update aborts rather than overwriting them — commit or stash your changes first.

### Manual update

```bash
cd /path/to/memcord
git pull
uv pip install -e . --upgrade
uv run python scripts/generate-config.py  # Regenerate configs

# Optional: Enable auto-save hooks
uv run python scripts/generate-config.py --install-hooks
```

## Security & Privacy

- **Local Storage Only**: All data stored locally on your machine
- **No Cloud Dependencies**: No external services or API calls
- **File Permissions**: Standard file system permissions apply
- **MCP Sandboxing**: Resources accessed through MCP security model
- **Search Index Privacy**: All indexing and search operations are local
- **No Data Transmission**: Tags, groups, and queries never leave your system