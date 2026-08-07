# Memcord Installation Script for Windows
# Run with: irm https://github.com/ukkit/memcord/raw/main/install.ps1 | iex
# Or: PowerShell -ExecutionPolicy Bypass -File install.ps1
# To pass -Scope through the piped form:
#   & ([scriptblock]::Create((irm https://github.com/ukkit/memcord/raw/main/install.ps1))) -Scope project

param(
    [string]$Scope
)

$ErrorActionPreference = "Stop"

# Validated manually rather than via [ValidateSet] on the param() above: when this
# script is piped into iex (the documented `irm ... | iex` usage), PowerShell binds
# $Scope to an empty string before any argument is supplied, and a ValidateSet
# attribute rejects that empty default immediately -- breaking even the plain,
# no-flags install command. An empty/unset $Scope is valid here (it means "let
# generate-config.py auto-detect"), so only a non-empty, invalid value is an error.
if ($Scope -and $Scope -notin @("project", "user")) {
    Write-Host "❌ Invalid -Scope value: '$Scope' (expected 'project' or 'user')" -ForegroundColor Red
    exit 1
}

$REPO_URL = "https://github.com/ukkit/memcord.git"

# Detect whether we're updating an existing install or doing a fresh one.
$isExistingRepo = (Test-Path "pyproject.toml") -and (Select-String -Path "pyproject.toml" -Pattern '^name = "memcord"' -Quiet) -and (Test-Path ".git")
if ($isExistingRepo) {
    $MODE = "update"
    $MEMCORD_PATH = (Get-Location).Path
} elseif (Test-Path "memcord/.git") {
    $MODE = "update"
    Set-Location memcord
    $MEMCORD_PATH = (Get-Location).Path
} else {
    $MODE = "install"
}

if ($MODE -eq "update") {
    Write-Host "🔄 Updating existing Memcord installation..." -ForegroundColor Cyan
    Write-Host "📍 Installation path: $MEMCORD_PATH" -ForegroundColor Green

    Write-Host "🔍 Checking for local modifications..." -ForegroundColor Yellow
    $dirty = git status --porcelain --untracked-files=no
    if ($dirty) {
        Write-Host "❌ Local changes detected in tracked files - update aborted to avoid overwriting them." -ForegroundColor Red
        Write-Host "   Review with: git -C `"$MEMCORD_PATH`" status" -ForegroundColor Gray
        Write-Host "   Commit or stash your changes, then re-run this installer." -ForegroundColor Gray
        exit 1
    }

    Write-Host "⬇️  Pulling latest changes..." -ForegroundColor Yellow
    git pull --ff-only
} else {
    Write-Host "🚀 Installing Memcord..." -ForegroundColor Cyan

    # Clone the repository
    Write-Host "📦 Cloning repository..." -ForegroundColor Yellow
    git clone $REPO_URL
    Set-Location memcord

    # Get the absolute path
    $MEMCORD_PATH = (Get-Location).Path
    Write-Host "📍 Installation path: $MEMCORD_PATH" -ForegroundColor Green
}

# Data protection check
Write-Host "🛡️  Checking for existing memory data..." -ForegroundColor Yellow
if (Test-Path "memory_slots") {
    $files = Get-ChildItem "memory_slots" -ErrorAction SilentlyContinue
    if ($files) {
        Write-Host "⚠️  EXISTING MEMORY DATA DETECTED!" -ForegroundColor Red
        Write-Host "📊 Running data protection script..." -ForegroundColor Yellow

        if (Test-Path "utilities/protect_data.py") {
            python utilities/protect_data.py --force
            if ($LASTEXITCODE -ne 0) {
                Write-Host "❌ Data protection failed - installation aborted!" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "🚨 Data protection script not found!" -ForegroundColor Red
            Write-Host "⚠️  Manual backup recommended:" -ForegroundColor Yellow
            $backupDate = Get-Date -Format "yyyyMMdd"
            Write-Host "   Copy-Item -Recurse memory_slots $env:USERPROFILE\backup_memory_slots_$backupDate" -ForegroundColor Gray

            $response = Read-Host "Continue anyway? [y/N]"
            if ($response -notmatch "^[Yy]$") {
                Write-Host "Installation cancelled for data safety." -ForegroundColor Yellow
                exit 1
            }
        }
    }
} else {
    Write-Host "✅ No existing memory data found - proceeding safely." -ForegroundColor Green
}

# Check if uv is installed
Write-Host "🔍 Checking for uv package manager..." -ForegroundColor Yellow
try {
    $uvVersion = uv --version 2>&1
    Write-Host "✅ Found uv: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠️  uv not found. Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# Create (or reuse) the virtual environment
if (Test-Path ".venv") {
    Write-Host "🐍 Using existing virtual environment..." -ForegroundColor Yellow
} else {
    Write-Host "🐍 Setting up Python virtual environment..." -ForegroundColor Yellow
    uv venv
}

# Activate virtual environment
Write-Host "📋 Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install/upgrade the package
Write-Host "📋 Installing memcord package..." -ForegroundColor Yellow
uv pip install -e . --upgrade

# Generate MCP configuration files using Python script
Write-Host "📝 Generating MCP configuration files..." -ForegroundColor Yellow
if (Test-Path "scripts/generate-config.py") {
    $scopeArgs = @()
    if ($Scope) { $scopeArgs = @("--scope", $Scope) }
    uv run python scripts/generate-config.py --install-path "$MEMCORD_PATH" --platform windows @scopeArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  Config generation had issues, but installation can continue." -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Config generator script not found - falling back to manual update" -ForegroundColor Yellow

    # Fallback: Update config files manually
    if (Test-Path "config-templates/claude-desktop/config.windows.json") {
        $config = Get-Content "config-templates/claude-desktop/config.windows.json" -Raw
        $config = $config -replace '\{\{MEMCORD_PATH\}\}', ($MEMCORD_PATH -replace '\\', '\\\\')
        $config | Set-Content "claude_desktop_config.json"
        Write-Host "✅ Updated claude_desktop_config.json" -ForegroundColor Green
    }

    if (Test-Path "config-templates/claude-code/mcp.windows.json") {
        $config = Get-Content "config-templates/claude-code/mcp.windows.json" -Raw
        $config = $config -replace '\{\{MEMCORD_PATH\}\}', ($MEMCORD_PATH -replace '\\', '\\\\')
        $config | Set-Content ".mcp.json"
        Write-Host "✅ Updated .mcp.json" -ForegroundColor Green
    }
}

# Update README.md with actual path
Write-Host "📝 Updating README.md with installation path..." -ForegroundColor Yellow
if (Test-Path "README.md") {
    $readme = Get-Content "README.md" -Raw
    $readme = $readme -replace '</path/to/memcord>', $MEMCORD_PATH
    $readme = $readme -replace '\{\{MEMCORD_PATH\}\}', $MEMCORD_PATH
    $readme | Set-Content "README.md"
    Write-Host "✅ Updated README.md with path: $MEMCORD_PATH" -ForegroundColor Green
} else {
    Write-Host "⚠️  README.md not found in repository" -ForegroundColor Yellow
}

Write-Host ""
if ($MODE -eq "update") {
    Write-Host "✨ Update complete!" -ForegroundColor Green
} else {
    Write-Host "✨ Installation complete!" -ForegroundColor Green
}
Write-Host "📂 Memcord installed at: $MEMCORD_PATH" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔧 Next steps:" -ForegroundColor Yellow
if ($MODE -eq "update") {
    Write-Host "   1. Restart Claude Desktop / your MCP client to load the updated server" -ForegroundColor Gray
    Write-Host "   2. In Claude Code, run: claude mcp list" -ForegroundColor Gray
} else {
    Write-Host "   1. Activate the virtual environment: & $MEMCORD_PATH\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host "   2. Restart Claude Desktop to load the MCP server" -ForegroundColor Gray
    Write-Host "   3. In Claude Code, run: claude mcp list" -ForegroundColor Gray
}
Write-Host ""
Write-Host "📚 Configuration files generated:" -ForegroundColor Yellow
Write-Host "   - Claude Code: project .mcp.json, or global ~/.claude.json if no .mcp.json existed yet" -ForegroundColor Gray
Write-Host "     (pass -Scope project or -Scope user to choose explicitly)" -ForegroundColor Gray
Write-Host "   - claude_desktop_config.json (Claude Desktop)" -ForegroundColor Gray
Write-Host "   - .vscode\mcp.json (VSCode/GitHub Copilot)" -ForegroundColor Gray
Write-Host "   - .antigravity\mcp_config.json (Google Antigravity IDE)" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 Optional: Enable auto-save hooks for Claude Code:" -ForegroundColor Yellow
Write-Host "   uv run python scripts/generate-config.py --install-hooks" -ForegroundColor Gray

if ($MODE -ne "update") {
    Write-Host ""
    if (-not [Console]::IsInputRedirected) {
        Write-Host "🧩 Slash commands:" -ForegroundColor Yellow
        uv run python scripts/generate-config.py --install-path "$MEMCORD_PATH" --manage-commands
    } else {
        Write-Host "🧩 Slash commands: run this later to install memcord-* commands globally:" -ForegroundColor Yellow
        Write-Host "   uv run python scripts/generate-config.py --install-path `"$MEMCORD_PATH`" --manage-commands" -ForegroundColor Gray
    }
}
Write-Host ""
Write-Host "📋 Claude Desktop config location:" -ForegroundColor Yellow
Write-Host "   Copy claude_desktop_config.json to:" -ForegroundColor Gray
Write-Host "   $env:APPDATA\Claude\claude_desktop_config.json" -ForegroundColor Cyan
