#!/bin/bash

set -e

REPO_URL="https://github.com/ukkit/memcord.git"

# Parse CLI args (works with: curl ... | bash -s -- --scope project)
SCOPE_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --scope)
            SCOPE_ARGS=(--scope "$2")
            shift 2
            ;;
        --scope=*)
            SCOPE_ARGS=(--scope "${1#*=}")
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Detect whether we're updating an existing install or doing a fresh one.
if [ -f "pyproject.toml" ] && grep -q '^name = "memcord"' pyproject.toml && [ -d ".git" ]; then
    MODE="update"
    MEMCORD_PATH=$(pwd)
elif [ -d "memcord/.git" ]; then
    MODE="update"
    cd memcord
    MEMCORD_PATH=$(pwd)
else
    MODE="install"
fi

if [ "$MODE" = "update" ]; then
    echo "Updating existing Memcord installation..."
    echo "Installation path: $MEMCORD_PATH"

    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        echo "❌ Local changes detected in tracked files - update aborted to avoid overwriting them."
        echo "   Review with: git -C \"$MEMCORD_PATH\" status"
        echo "   Commit or stash your changes, then re-run this installer."
        exit 1
    fi

    echo "Pulling latest changes..."
    git pull --ff-only
else
    echo "Installing Memcord..."

    # Clone the repository
    echo "Cloning repository..."
    git clone "$REPO_URL"
    cd memcord

    # Get the absolute path
    MEMCORD_PATH=$(pwd)
    echo "Installation path: $MEMCORD_PATH"
fi

# Data protection check
if [ -d "memory_slots" ] && [ "$(ls -A memory_slots 2>/dev/null)" ]; then
    echo "Existing memory data found - creating automatic backup..."

    if [ -f "utilities/protect_data.py" ]; then
        python3 utilities/protect_data.py --force --backup-only
        if [ $? -ne 0 ]; then
            echo "❌ Data protection failed - installation aborted!"
            exit 1
        fi
    else
        echo "⚠️  Data protection script not found. Manual backup recommended:"
        echo "   cp -r memory_slots ~/backup_memory_slots_$(date +%Y%m%d)"
        read -p "Continue anyway? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled for data safety."
            exit 1
        fi
    fi
fi

# Create (or reuse) the virtual environment
if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment..."
    uv venv
fi
source .venv/bin/activate

# Install/upgrade the package
echo "Installing memcord package..."
uv pip install -e . --upgrade

# Generate MCP configuration files using Python script
echo "Generating MCP configuration files..."
if [ -f "scripts/generate-config.py" ]; then
    uv run python scripts/generate-config.py --install-path "$MEMCORD_PATH" "${SCOPE_ARGS[@]}"
    if [ $? -ne 0 ]; then
        echo "⚠️  Config generation had issues, but installation can continue."
    fi
else
    echo "⚠️  Config generator script not found - falling back to manual update"
    # Fallback: Update claude_desktop_config.json with actual path
    if [ -f "claude_desktop_config.json" ]; then
        sed "s|{{MEMCORD_PATH}}|$MEMCORD_PATH|g" claude_desktop_config.json > claude_desktop_config.json.tmp && mv claude_desktop_config.json.tmp claude_desktop_config.json
        echo "✅ Updated claude_desktop_config.json"
    fi
fi

# Update README.md with actual path (for documentation purposes)
if [ -f "README.md" ]; then
    # Replace both old placeholder format and new placeholder format
    sed -e "s|</path/to/memcord>|$MEMCORD_PATH|g" \
        -e "s|{{MEMCORD_PATH}}|$MEMCORD_PATH|g" \
        README.md > README.md.tmp && mv README.md.tmp README.md
else
    echo "⚠️  README.md not found in repository"
fi

echo ""
if [ "$MODE" = "update" ]; then
    echo "✅ Update complete!"
else
    echo "✅ Installation complete!"
fi
echo "Memcord installed at: $MEMCORD_PATH"
echo ""
echo "Next steps:"
if [ "$MODE" = "update" ]; then
    echo "   1. Restart Claude Desktop / your MCP client to load the updated server"
    echo "   2. In Claude Code, run: claude mcp list"
else
    echo "   1. Activate the virtual environment: source $MEMCORD_PATH/.venv/bin/activate"
    echo "   2. Restart Claude Desktop to load the MCP server"
    echo "   3. In Claude Code, run: claude mcp list"
fi
echo ""
echo "Configuration files generated:"
echo "   - Claude Code: project .mcp.json, or global ~/.claude.json if no .mcp.json existed yet"
echo "     (pass --scope project or --scope user to choose explicitly)"
echo "   - claude_desktop_config.json (Claude Desktop)"
echo "   - .vscode/mcp.json (VSCode/GitHub Copilot)"
echo "   - .antigravity/mcp_config.json (Google Antigravity IDE)"
echo ""
echo "Optional: Enable auto-save hooks for Claude Code:"
echo "   uv run python scripts/generate-config.py --install-hooks"

echo ""
if [ -t 0 ] && [ "$MODE" != "update" ]; then
    echo "Slash commands:"
    uv run python scripts/generate-config.py --install-path "$MEMCORD_PATH" --manage-commands
else
    echo "Slash commands: run this to choose which memcord-* commands to install globally:"
    echo "   uv run python scripts/generate-config.py --install-path \"$MEMCORD_PATH\" --manage-commands"
fi
