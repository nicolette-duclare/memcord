#!/usr/bin/env python3
"""
Cross-platform MCP configuration generator for memcord.

This script generates platform-appropriate MCP configuration files
by replacing {{MEMCORD_PATH}} placeholders with the actual installation path.

Usage:
    python scripts/generate-config.py                    # Auto-detect path
    python scripts/generate-config.py --install-path /path/to/memcord
    python scripts/generate-config.py --platform windows  # Force platform
"""

import argparse
import filecmp
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, cast

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# ANSI colors (disabled on Windows unless terminal supports it)
if IS_WINDOWS:
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        COLORS_ENABLED = True
    except Exception:
        COLORS_ENABLED = False
else:
    COLORS_ENABLED = True


def color(text: str, code: str) -> str:
    """Apply ANSI color code to text."""
    if not COLORS_ENABLED:
        return text
    codes = {"green": "32", "yellow": "33", "red": "31", "cyan": "36", "bold": "1"}
    return f"\033[{codes.get(code, '0')}m{text}\033[0m"


def get_memcord_path() -> Path:
    """Get the memcord installation directory."""
    # Script is in scripts/, so parent is memcord root
    return Path(__file__).parent.parent.resolve()


def get_claude_desktop_config_path() -> Path | None:
    """Get the Claude Desktop config file path for current platform."""
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif IS_WINDOWS:
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif IS_LINUX:
        # Linux uses XDG config or .config
        xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        return Path(xdg_config) / "Claude" / "claude_desktop_config.json"
    return None


def get_claude_code_config_path() -> Path | None:
    """Get the Claude Code .mcp.json path (project-level)."""
    return get_memcord_path() / ".mcp.json"


def get_claude_code_user_config_path() -> Path:
    """Get the Claude Code user-level config path (global MCP server scope).

    Same location on all platforms.
    """
    return Path.home() / ".claude.json"


def get_user_commands_dir() -> Path:
    """Get the global Claude Code slash-commands directory (same on all platforms)."""
    return Path.home() / ".claude" / "commands"


def get_available_commands(memcord_path: Path) -> list[Path]:
    """Return the shipped memcord-*.md command source files, sorted by filename.

    The glob pattern is the whole manifest boundary -- toon-*.md and anything else
    under .claude/commands/ is never matched, listed, copied, or removed.
    """
    commands_dir = memcord_path / ".claude" / "commands"
    if not commands_dir.exists():
        return []
    return sorted(commands_dir.glob("memcord-*.md"), key=lambda p: p.name)


def _read_command_description(path: Path) -> str:
    """Pull the `description:` value out of a command file's YAML frontmatter.

    Lightweight line-scan (frontmatter is always `---\\ndescription: ...\\n---` in
    these files) -- avoids adding a yaml dependency for one field. Falls back to the
    filename stem if the field is missing or unparsable.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return path.stem

    in_frontmatter = False
    for line in lines:
        if line.strip() == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if in_frontmatter and line.startswith("description:"):
            return line.split(":", 1)[1].strip()

    return path.stem


def apply_command_selection(
    memcord_path: Path,
    target_dir: Path,
    selected_names: set[str],
    dry_run: bool = False,
    verbose: bool = True,
) -> bool:
    """Reconcile target_dir with the desired set of installed memcord command filenames.

    - Files in selected_names are copied (atomically) from .claude/commands/, always
      overwriting -- idempotent re-apply, and re-running picks up upstream command
      updates, matching install_hooks()'s always-rewrite semantics.
    - Files in (available - selected_names) that currently exist in target_dir are
      removed -- unless their content no longer matches the shipped source (the user
      hand-edited it), in which case they're renamed to <name>.bak instead of deleted,
      so edits are never silently discarded.
    - Every other file in target_dir (anything not an exact filename match against the
      current manifest) is never read, written, or deleted -- this is the ownership
      boundary. A user's own ~/.claude/commands/memcord-custom-thing.md is left alone
      even though it starts with "memcord-", because it isn't one of the shipped files.
    """
    available_paths = {p.name: p for p in get_available_commands(memcord_path)}
    available_names = set(available_paths.keys())
    selected_names = selected_names & available_names

    success = True

    for name in sorted(selected_names):
        source = available_paths[name]
        dest = target_dir / name
        if dry_run:
            print(f"  {color('[DRY RUN]', 'yellow')} Would install: {dest}")
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = dest.with_name(dest.name + ".tmp")
            shutil.copy2(source, tmp_path)
            os.replace(tmp_path, dest)
            if verbose:
                print(f"  {color('Installed:', 'green')} {dest}")
        except OSError as e:
            print(f"  {color('Error:', 'red')} Failed to install {dest}: {e}")
            success = False

    for name in sorted(available_names - selected_names):
        dest = target_dir / name
        if not dest.exists():
            continue
        source = available_paths[name]
        if dry_run:
            print(f"  {color('[DRY RUN]', 'yellow')} Would remove: {dest}")
            continue
        try:
            if filecmp.cmp(source, dest, shallow=False):
                dest.unlink()
                if verbose:
                    print(f"  {color('Removed:', 'yellow')} {dest}")
            else:
                backup_path = dest.with_name(dest.name + ".bak")
                os.replace(dest, backup_path)
                if verbose:
                    print(f"  {color('Backed up (edited):', 'cyan')} {dest} -> {backup_path}")
        except OSError as e:
            print(f"  {color('Error:', 'red')} Failed to remove {dest}: {e}")
            success = False

    return success


def _prompt_command_toggle(prompt: str) -> str | None:
    """Read one line of picker input, returning None on EOF/interrupt."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None


def manage_commands_interactive(memcord_path: Path, target_dir: Path, dry_run: bool = False) -> bool:
    """Interactively choose which memcord-* commands are installed at target_dir."""
    available = get_available_commands(memcord_path)
    if not available:
        commands_dir = memcord_path / ".claude" / "commands"
        print(f"  {color('Warning:', 'yellow')} No memcord-*.md commands found under {commands_dir}")
        return True

    if not sys.stdin.isatty():
        print(
            "  Skipping interactive command picker (non-interactive session). "
            "Run 'uv run python scripts/generate-config.py --manage-commands' later, "
            "or use --commands all|none|name1,name2."
        )
        return True

    installed = {p.name for p in available if (target_dir / p.name).exists()}
    selected = set(installed)

    print(f"\n{color('Memcord Slash Commands', 'bold')} ({target_dir})")
    print("=" * 40)

    while True:
        for i, path in enumerate(available, start=1):
            mark = "x" if path.name in selected else " "
            desc = _read_command_description(path)
            print(f" [{mark}] {i:2d}. {path.name:<28} {desc}")
        print(
            "\nToggle: enter numbers (space/comma separated), 'a' = select all,\n"
            "'n' = select none, 'y' or Enter = apply and exit, 'q' = quit without changes"
        )
        line = _prompt_command_toggle("> ")
        if line is None:
            print("\nCancelled -- no changes made.")
            return True

        tokens = [t for t in line.replace(",", " ").split() if t]
        if not tokens:
            break

        lowered = {t.lower() for t in tokens}
        if lowered <= {"y", "yes"}:
            break
        if lowered <= {"q", "quit"}:
            print("No changes made.")
            return True
        if lowered <= {"a", "all"}:
            selected = {p.name for p in available}
            continue
        if lowered <= {"n", "none"}:
            selected = set()
            continue

        unrecognized = []
        for token in tokens:
            if token.isdigit() and 1 <= int(token) <= len(available):
                name = available[int(token) - 1].name
                if name in selected:
                    selected.discard(name)
                else:
                    selected.add(name)
            else:
                unrecognized.append(token)
        for token in unrecognized:
            print(f"Unrecognized input: '{token}'")

    result = apply_command_selection(memcord_path, target_dir, selected, dry_run=dry_run, verbose=True)
    added = selected - installed
    removed = installed - selected
    if not added and not removed:
        print("Unchanged.")
    return result


def parse_commands_arg(value: str, available_names: list[str]) -> set[str]:
    """Parse --commands all|none|name1,name2,... into a set of shipped filenames.

    Accepts both "memcord-save" and "memcord-save.md" for each token. Raises
    ValueError (with the list of valid names) on any token that isn't a match.
    """
    lowered = value.strip().lower()
    if lowered == "all":
        return set(available_names)
    if lowered == "none":
        return set()

    available_set = set(available_names)
    selected = set()
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        candidate = token if token.endswith(".md") else f"{token}.md"
        if candidate not in available_set:
            valid = ", ".join(sorted(n[: -len(".md")] for n in available_set))
            raise ValueError(f"Unknown command '{token}'. Valid names: {valid}")
        selected.add(candidate)
    return selected


def load_template(template_path: Path) -> dict[str, Any]:
    """Load a JSON template file."""
    with open(template_path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def replace_placeholders(config: dict[str, Any], memcord_path: str, use_backslashes: bool = False) -> dict[str, Any]:
    """Replace {{MEMCORD_PATH}} placeholders in config."""
    config_str = json.dumps(config)

    # Normalize path for the platform
    if use_backslashes:
        # Windows: use double backslashes in JSON
        path_for_json = memcord_path.replace("\\", "\\\\")
    else:
        # Unix: use forward slashes
        path_for_json = memcord_path.replace("\\", "/")

    config_str = config_str.replace("{{MEMCORD_PATH}}", path_for_json)
    return cast(dict[str, Any], json.loads(config_str))


def save_config(config: dict, output_path: Path, dry_run: bool = False) -> bool:
    """Save configuration to file.

    Writes atomically (temp file + replace) so an interrupted write never leaves the
    target file partially written — important for files like ~/.claude.json that are
    critical, shared state rather than disposable generated config.
    """
    if dry_run:
        print(f"  {color('[DRY RUN]', 'yellow')} Would write to: {output_path}")
        return True

    tmp_path = output_path.with_name(output_path.name + ".tmp")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, output_path)
        return True
    except Exception as e:
        print(f"  {color('Error:', 'red')} Failed to write {output_path}: {e}")
        tmp_path.unlink(missing_ok=True)
        return False


def backup_file(path: Path, dry_run: bool = False, verbose: bool = True) -> None:
    """Create a single rolling backup (path + '.bak') of an existing file before modifying it.

    No-op if the file doesn't exist yet. Used before merging into files we don't own
    the format of (e.g. ~/.claude.json) so a bad merge is always recoverable.
    """
    if not path.exists():
        return
    backup_path = path.with_name(path.name + ".bak")
    if dry_run:
        if verbose:
            print(f"  {color('[DRY RUN]', 'yellow')} Would back up {path} to {backup_path}")
        return
    shutil.copy2(path, backup_path)


def load_hooks_template(templates_dir: Path) -> dict[str, Any]:
    """Load the Claude Code hooks template."""
    hooks_path = templates_dir / "claude-code" / "hooks.json"
    if not hooks_path.exists():
        print(f"  {color('Error:', 'red')} Hooks template not found: {hooks_path}")
        return {}
    return load_template(hooks_path)


def _is_memcord_hook(hook: dict[str, Any]) -> bool:
    """Detect a memcord hook in either old or new Claude Code format.

    Old format: {"type": "agent", "description": "memcord: ...", "prompt": "..."}
    New format: {"hooks": [{"type": "agent", "description": "memcord: ...", "prompt": "..."}]}
    """
    # Old format: description directly on the outer object
    if hook.get("description", "").startswith("memcord:"):
        return True
    # New format: description inside nested hooks array
    for h in hook.get("hooks", []):
        if h.get("description", "").startswith("memcord:"):
            return True
    return False


def merge_hooks(existing: dict[str, Any], new_hooks: dict[str, Any]) -> dict[str, Any]:
    """Merge memcord hooks into existing Claude Code settings.

    Deduplicates by checking for 'memcord:' prefix in hook descriptions.
    Handles both old format (description on outer object) and new format
    (description inside nested hooks array). Preserves all non-memcord hooks.

    Also removes memcord hooks from events no longer present in the template,
    so re-running --install-hooks cleans up stale hooks from removed events.
    """
    result = existing.copy()

    if "hooks" not in new_hooks:
        return result

    if "hooks" not in result:
        result["hooks"] = {}

    template_events = set(new_hooks["hooks"].keys())

    # Remove memcord hooks from events no longer in the template (cleanup pass)
    for event_key in list(result["hooks"].keys()):
        if event_key not in template_events:
            result["hooks"][event_key] = [hook for hook in result["hooks"][event_key] if not _is_memcord_hook(hook)]

    for event_key, hook_entries in new_hooks["hooks"].items():
        if event_key not in result["hooks"]:
            result["hooks"][event_key] = []

        # Remove existing memcord hooks in either format (deduplication)
        result["hooks"][event_key] = [hook for hook in result["hooks"][event_key] if not _is_memcord_hook(hook)]

        # Add new memcord hooks
        result["hooks"][event_key].extend(hook_entries)

    return result


def install_hooks(
    memcord_path: Path,
    templates_dir: Path,
    dry_run: bool = False,
    verbose: bool = True,
) -> bool:
    """Install Claude Code agent hooks for auto-save."""
    if verbose:
        print(f"\n{color('[Hooks]', 'green')} Claude Code Auto-Save Hooks")

    hooks_template = load_hooks_template(templates_dir)
    if not hooks_template:
        return False

    settings_path = memcord_path / ".claude" / "settings.json"

    # Load existing settings or start fresh
    existing = {}
    if settings_path.exists():
        try:
            existing = load_template(settings_path)
        except Exception as e:
            if verbose:
                print(f"  {color('Warning:', 'yellow')} Could not read existing settings: {e}")
            existing = {}

    merged = merge_hooks(existing, hooks_template)

    if dry_run:
        print(f"  {color('[DRY RUN]', 'yellow')} Would write hooks to: {settings_path}")
        if verbose:
            hook_events = list(hooks_template.get("hooks", {}).keys())
            print(f"  Hook events: {', '.join(hook_events)}")
        return True

    if save_config(merged, settings_path):
        if verbose:
            print(f"  {color('Installed:', 'green')} {settings_path}")
            hook_events = list(hooks_template.get("hooks", {}).keys())
            print(f"  Hook events: {', '.join(hook_events)}")
        return True
    return False


def merge_mcp_servers(existing: dict, new_servers: dict) -> dict:
    """Merge new MCP servers into existing config without overwriting other servers."""
    result = existing.copy()

    # Handle both "mcpServers" and "servers" keys
    for key in ["mcpServers", "servers"]:
        if key in new_servers:
            if key not in result:
                result[key] = {}
            result[key].update(new_servers[key])

    return result


def generate_configs(
    memcord_path: Path,
    force_platform: str | None = None,
    install_claude_desktop: bool = True,
    install_claude_code: bool = True,
    scope: str = "user",
    dry_run: bool = False,
    verbose: bool = True,
) -> bool:
    """Generate all configuration files.

    scope controls where Claude Code registration goes: "project" writes .mcp.json
    next to the memcord checkout (team sharing via version control); "user" merges
    into ~/.claude.json so memcord is available in every project.
    """

    templates_dir = memcord_path / "config-templates"
    if not templates_dir.exists():
        print(f"{color('Error:', 'red')} config-templates directory not found at {templates_dir}")
        return False

    # Determine platform
    if force_platform:
        is_windows = force_platform.lower() == "windows"
    else:
        is_windows = IS_WINDOWS

    platform_name = "Windows" if is_windows else ("macOS" if IS_MACOS else "Linux")
    path_str = str(memcord_path)

    if verbose:
        print(f"\n{color('Memcord Configuration Generator', 'bold')}")
        print(f"{'=' * 40}")
        print(f"Platform: {color(platform_name, 'cyan')}")
        print(f"Memcord path: {color(path_str, 'cyan')}")
        if install_claude_code:
            print(f"Claude Code scope: {color(scope, 'cyan')}")
        print()

    success = True

    # 1. Generate Claude Desktop config
    if install_claude_desktop:
        if verbose:
            print(f"{color('[1/2]', 'green')} Claude Desktop Configuration")

        template_name = "config.windows.json" if is_windows else "config.json"
        template_path = templates_dir / "claude-desktop" / template_name

        if template_path.exists():
            template = load_template(template_path)
            config = replace_placeholders(template, path_str, use_backslashes=is_windows)

            # Save to project directory (for reference)
            project_config = memcord_path / "claude_desktop_config.json"
            if save_config(config, project_config, dry_run):
                if verbose:
                    print(f"  {color('Created:', 'green')} {project_config}")
            else:
                success = False

            # Also save/merge to system Claude Desktop config location
            system_config_path = get_claude_desktop_config_path()
            if system_config_path:
                if system_config_path.exists():
                    try:
                        existing = load_template(system_config_path)
                        merged = merge_mcp_servers(existing, config)
                        if save_config(merged, system_config_path, dry_run):
                            if verbose:
                                print(f"  {color('Merged into:', 'green')} {system_config_path}")
                    except Exception as e:
                        if verbose:
                            print(f"  {color('Note:', 'yellow')} Could not merge into system config: {e}")
                else:
                    if verbose:
                        print(f"  {color('Note:', 'yellow')} System config not found at {system_config_path}")
                        print(f"       Copy {project_config} there after Claude Desktop is installed.")
        else:
            print(f"  {color('Warning:', 'yellow')} Template not found: {template_path}")

    # 2. Configure Claude Code (project .mcp.json or user-level ~/.claude.json)
    if install_claude_code:
        if verbose:
            print(f"\n{color('[2/2]', 'green')} Claude Code Configuration ({scope} scope)")

        template_name = "mcp.windows.json" if is_windows else "mcp.json"
        template_path = templates_dir / "claude-code" / template_name

        if template_path.exists():
            template = load_template(template_path)
            config = replace_placeholders(template, path_str, use_backslashes=False)

            if scope == "project":
                output_path = memcord_path / ".mcp.json"
                if save_config(config, output_path, dry_run):
                    if verbose:
                        print(f"  {color('Created:', 'green')} {output_path}")
                else:
                    success = False
            else:
                # User scope: merge into Claude Code's global config, touching only
                # the mcpServers key so unrelated user state is left untouched.
                user_config_path = get_claude_code_user_config_path()
                had_existing = user_config_path.exists()
                existing_user_config: dict[str, Any] = {}
                read_ok = True
                if had_existing:
                    try:
                        existing_user_config = load_template(user_config_path)
                    except Exception as e:
                        print(f"  {color('Error:', 'red')} Could not read {user_config_path}: {e}")
                        read_ok = False

                if read_ok:
                    merged = merge_mcp_servers(existing_user_config, config)
                    backup_file(user_config_path, dry_run, verbose)
                    if save_config(merged, user_config_path, dry_run):
                        if verbose:
                            print(f"  {color('Registered globally in:', 'green')} {user_config_path}")
                            if had_existing and not dry_run:
                                print(f"  {color('Backup saved to:', 'cyan')} {user_config_path}.bak")
                    else:
                        success = False
                else:
                    success = False
        else:
            print(f"  {color('Warning:', 'yellow')} Template not found: {template_path}")

    # 3. Copy VSCode config (uses ${workspaceFolder}, no path replacement needed)
    vscode_template = templates_dir / "vscode" / "mcp.json"
    vscode_dest = memcord_path / ".vscode" / "mcp.json"
    if vscode_template.exists():
        if not dry_run:
            vscode_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vscode_template, vscode_dest)
        if verbose:
            print(f"\n{color('[Bonus]', 'green')} VSCode/GitHub Copilot Configuration")
            print(f"  {color('Created:', 'green')} {vscode_dest}")

    # 4. Update Antigravity config
    antigravity_template = templates_dir / "antigravity" / "mcp_config.json"
    antigravity_dest = memcord_path / ".antigravity" / "mcp_config.json"
    if antigravity_template.exists():
        template = load_template(antigravity_template)
        config = replace_placeholders(template, path_str, use_backslashes=False)  # Antigravity uses Unix paths
        if save_config(config, antigravity_dest, dry_run):
            if verbose:
                print(f"\n{color('[Bonus]', 'green')} Google Antigravity IDE Configuration")
                print(f"  {color('Created:', 'green')} {antigravity_dest}")

    if verbose:
        print(f"\n{'=' * 40}")
        if success:
            print(f"{color('Configuration complete!', 'green')}")
            print("\nNext steps:")
            print("  1. Restart Claude Desktop (if using)")
            print(f"  2. Run: {color('claude mcp list', 'cyan')} to verify Claude Code sees memcord")
            print(f"  3. Test with: {color('/mcp', 'cyan')} command in Claude Code")
        else:
            print(f"{color('Configuration completed with errors.', 'yellow')}")

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Generate MCP configuration files for memcord",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate-config.py                     # Auto-detect everything
  python scripts/generate-config.py --dry-run           # Preview changes
  python scripts/generate-config.py --platform windows  # Force Windows configs
  python scripts/generate-config.py --install-path /custom/path
        """,
    )

    parser.add_argument("--install-path", type=str, help="Override the memcord installation path")

    parser.add_argument(
        "--platform", choices=["windows", "unix", "auto"], default="auto", help="Force platform (default: auto-detect)"
    )

    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output except errors")

    parser.add_argument("--no-claude-desktop", action="store_true", help="Skip Claude Desktop configuration")

    parser.add_argument("--no-claude-code", action="store_true", help="Skip Claude Code .mcp.json configuration")

    parser.add_argument(
        "--scope",
        choices=["project", "user"],
        default=None,
        help="Claude Code registration scope: 'project' writes .mcp.json next to the memcord "
        "checkout (team sharing via version control); 'user' registers memcord globally in "
        "~/.claude.json for every project. Default: auto-detect -- 'project' if a .mcp.json "
        "already exists here, otherwise 'user'.",
    )

    parser.add_argument(
        "--install-hooks",
        action="store_true",
        help="Install Claude Code agent hooks for auto-save on compaction and session end",
    )

    commands_group = parser.add_mutually_exclusive_group()
    commands_group.add_argument(
        "--manage-commands",
        action="store_true",
        help="Interactively choose which memcord-* slash commands to install globally into "
        "~/.claude/commands/ (skips automatically in non-interactive sessions).",
    )
    commands_group.add_argument(
        "--commands",
        metavar="all|none|name1,name2,...",
        default=None,
        help="Non-interactive alternative to --manage-commands: apply this exact selection "
        "of memcord-* command filenames to ~/.claude/commands/ without prompting.",
    )

    args = parser.parse_args()

    # Determine memcord path
    if args.install_path:
        memcord_path = Path(args.install_path).resolve()
    else:
        memcord_path = get_memcord_path()

    # Validate path
    if not memcord_path.exists():
        print(f"{color('Error:', 'red')} Memcord path does not exist: {memcord_path}")
        sys.exit(1)

    # Determine platform override
    force_platform = None
    if args.platform != "auto":
        force_platform = args.platform

    # Determine Claude Code scope: honor an explicit choice, otherwise auto-detect from
    # whether this checkout already has a project-level .mcp.json (preserves existing
    # team-shared setups on update; defaults fresh installs to global/user scope).
    scope = args.scope
    if scope is None:
        scope = "project" if (memcord_path / ".mcp.json").exists() else "user"

    # Generate configs
    success = generate_configs(
        memcord_path=memcord_path,
        force_platform=force_platform,
        install_claude_desktop=not args.no_claude_desktop,
        install_claude_code=not args.no_claude_code,
        scope=scope,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )

    # Install hooks if requested
    if args.install_hooks:
        templates_dir = memcord_path / "config-templates"
        hooks_ok = install_hooks(
            memcord_path=memcord_path,
            templates_dir=templates_dir,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )
        if not hooks_ok:
            success = False

    # Manage slash commands if requested
    if args.commands is not None:
        available_names = [p.name for p in get_available_commands(memcord_path)]
        try:
            selected = parse_commands_arg(args.commands, available_names)
        except ValueError as e:
            print(f"{color('Error:', 'red')} {e}")
            sys.exit(1)
        commands_ok = apply_command_selection(
            memcord_path=memcord_path,
            target_dir=get_user_commands_dir(),
            selected_names=selected,
            dry_run=args.dry_run,
            verbose=not args.quiet,
        )
        if not commands_ok:
            success = False
    elif args.manage_commands:
        commands_ok = manage_commands_interactive(
            memcord_path=memcord_path,
            target_dir=get_user_commands_dir(),
            dry_run=args.dry_run,
        )
        if not commands_ok:
            success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
