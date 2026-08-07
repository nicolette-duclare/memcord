"""
Tests for installation scripts and configuration generator.

These tests verify that:
- install.sh (Bash) has correct structure and functionality
- install.ps1 (PowerShell) has correct structure and functionality
- scripts/generate-config.py works correctly for all platforms
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# =============================================================================
# Test install.sh (Bash Installation Script) - 12 tests
# =============================================================================


class TestInstallShScript:
    """Tests for the install.sh Bash installation script."""

    @pytest.fixture
    def script_path(self):
        """Get the path to install.sh."""
        return Path("install.sh")

    @pytest.fixture
    def script_content(self, script_path):
        """Load the install.sh script content."""
        with open(script_path, encoding="utf-8") as f:
            return f.read()

    def test_script_exists(self, script_path):
        """Test that install.sh exists in the repository root."""
        assert script_path.exists(), "install.sh should exist in repository root"

    def test_script_has_shebang(self, script_content):
        """Test that install.sh starts with proper bash shebang."""
        assert script_content.startswith("#!/bin/bash"), "install.sh should start with #!/bin/bash shebang"

    def test_script_uses_set_e(self, script_content):
        """Test that install.sh uses 'set -e' for error handling."""
        assert "set -e" in script_content, "install.sh should use 'set -e' to exit on errors"

    def test_script_clones_correct_repo(self, script_content):
        """Test that install.sh clones from the correct GitHub repository."""
        assert "https://github.com/ukkit/memcord.git" in script_content, (
            "install.sh should reference correct GitHub URL"
        )
        assert "git clone" in script_content, "install.sh should clone the repository"

    def test_script_checks_existing_data(self, script_content):
        """Test that install.sh checks for existing memory_slots data."""
        assert "memory_slots" in script_content, "install.sh should check for existing memory_slots directory"
        assert "Existing memory data found" in script_content, "install.sh should warn about existing data"

    def test_script_runs_data_protection(self, script_content):
        """Test that install.sh runs data protection script when needed."""
        assert "utilities/protect_data.py" in script_content, "install.sh should reference data protection script"
        assert "python3 utilities/protect_data.py" in script_content, (
            "install.sh should run data protection with python3"
        )
        assert "--backup-only" in script_content, (
            "install.sh should pass --backup-only so protect_data.py skips its warning/options display "
            "(the installer always creates a backup, so that display adds no value)"
        )

    def test_script_creates_venv(self, script_content):
        """Test that install.sh creates virtual environment with uv."""
        assert "uv venv" in script_content, "install.sh should create virtual environment with uv"
        assert "source .venv/bin/activate" in script_content, "install.sh should activate the virtual environment"

    def test_script_installs_package(self, script_content):
        """Test that install.sh installs the memcord package."""
        assert "uv pip install -e ." in script_content, "install.sh should install memcord in editable mode"

    def test_script_calls_config_generator(self, script_content):
        """Test that install.sh calls the config generator script."""
        assert "scripts/generate-config.py" in script_content, "install.sh should call generate-config.py"
        assert "--install-path" in script_content, "install.sh should pass --install-path to config generator"

    def test_script_updates_readme(self, script_content):
        """Test that install.sh updates README.md with installation path."""
        assert "README.md" in script_content, "install.sh should reference README.md"
        assert "{{MEMCORD_PATH}}" in script_content, "install.sh should replace {{MEMCORD_PATH}} placeholder"

    def test_script_shows_next_steps(self, script_content):
        """Test that install.sh displays next steps after installation."""
        assert "Next steps:" in script_content, "install.sh should show next steps"
        assert "Restart Claude Desktop" in script_content, "install.sh should mention restarting Claude Desktop"
        assert "claude mcp list" in script_content, "install.sh should mention 'claude mcp list' command"

    def test_script_lists_generated_configs(self, script_content):
        """Test that install.sh lists all generated configuration files."""
        assert ".mcp.json" in script_content, "install.sh should mention .mcp.json"
        assert "claude_desktop_config.json" in script_content, "install.sh should mention claude_desktop_config.json"
        assert ".vscode/mcp.json" in script_content, "install.sh should mention .vscode/mcp.json"
        assert ".antigravity/mcp_config.json" in script_content, (
            "install.sh should mention .antigravity/mcp_config.json"
        )

    def test_script_detects_existing_install(self, script_content):
        """Test that install.sh detects an existing checkout and updates it instead of re-cloning."""
        assert 'MODE="update"' in script_content, "install.sh should support an update mode"
        assert "memcord/.git" in script_content, "install.sh should detect an existing memcord clone"
        assert "git pull --ff-only" in script_content, "install.sh should fast-forward pull on update"

    def test_script_refuses_update_with_local_changes(self, script_content):
        """Test that install.sh aborts an update rather than clobbering local modifications."""
        assert "git status --porcelain" in script_content, "install.sh should check for local modifications"
        assert "update aborted" in script_content, "install.sh should abort the update when local changes exist"

    def test_script_reuses_existing_venv(self, script_content):
        """Test that install.sh reuses an existing virtual environment on update."""
        assert '-d ".venv"' in script_content, "install.sh should check for an existing .venv before creating one"

    def test_script_passes_scope_arg_through(self, script_content):
        """Test that install.sh accepts and forwards --scope to generate-config.py."""
        assert "SCOPE_ARGS" in script_content, "install.sh should collect a --scope argument"
        assert '"${SCOPE_ARGS[@]}"' in script_content, "install.sh should forward SCOPE_ARGS to generate-config.py"

    def test_script_offers_command_picker_on_fresh_install(self, script_content):
        """Test that install.sh auto-invokes the command picker on a fresh, interactive install only."""
        assert "[ -t 0 ]" in script_content, "install.sh should gate the picker on stdin being a real terminal"
        assert "--manage-commands" in script_content, "install.sh should invoke --manage-commands"
        assert '"$MODE" != "update"' in script_content, (
            "install.sh should only auto-invoke the picker on fresh installs"
        )

    def test_script_shows_command_hint_on_update_too(self, script_content):
        """Regression test: update runs must still mention the command picker (a hint, not
        an auto-prompt) -- the whole slash-commands block used to be wrapped in a single
        `[ "$MODE" != "update" ]` guard, so update runs got no mention of it at all, not
        even the manual-command hint."""
        assert "choose which memcord-* commands to install globally" in script_content, (
            "install.sh should show a hint about --manage-commands on update runs too"
        )


# =============================================================================
# Test install.ps1 (PowerShell Installation Script) - 12 tests
# =============================================================================


class TestInstallPs1Script:
    """Tests for the install.ps1 PowerShell installation script."""

    @pytest.fixture
    def script_path(self):
        """Get the path to install.ps1."""
        return Path("install.ps1")

    @pytest.fixture
    def script_content(self, script_path):
        """Load the install.ps1 script content."""
        with open(script_path, encoding="utf-8") as f:
            return f.read()

    def test_script_exists(self, script_path):
        """Test that install.ps1 exists in the repository root."""
        assert script_path.exists(), "install.ps1 should exist in repository root"

    def test_script_uses_error_action_stop(self, script_content):
        """Test that install.ps1 uses ErrorActionPreference Stop."""
        assert '$ErrorActionPreference = "Stop"' in script_content, (
            "install.ps1 should set ErrorActionPreference to Stop"
        )

    def test_script_clones_correct_repo(self, script_content):
        """Test that install.ps1 clones from the correct GitHub repository."""
        assert "https://github.com/ukkit/memcord.git" in script_content, (
            "install.ps1 should reference correct GitHub URL"
        )
        assert "git clone" in script_content, "install.ps1 should clone the repository"

    def test_script_checks_existing_data(self, script_content):
        """Test that install.ps1 checks for existing memory_slots data."""
        assert "memory_slots" in script_content, "install.ps1 should check for existing memory_slots directory"
        assert "Existing memory data found" in script_content, "install.ps1 should warn about existing data"

    def test_script_runs_data_protection(self, script_content):
        """Test that install.ps1 runs data protection script when needed."""
        assert "utilities/protect_data.py" in script_content, "install.ps1 should reference data protection script"
        assert "python utilities/protect_data.py" in script_content, (
            "install.ps1 should run data protection with python"
        )
        assert "--backup-only" in script_content, (
            "install.ps1 should pass --backup-only so protect_data.py skips its warning/options display "
            "(the installer always creates a backup, so that display adds no value)"
        )

    def test_script_forces_python_utf8(self, script_content):
        """Test that install.ps1 forces UTF-8 for child Python processes.

        On a legacy (non-UTF-8) Windows console codepage, protect_data.py's status
        emoji can raise UnicodeEncodeError after the real work (e.g. the backup)
        already succeeded, turning a successful step into a false abort."""
        assert "PYTHONUTF8" in script_content, "install.ps1 should set $env:PYTHONUTF8 for child Python processes"

    def test_script_checks_uv_installed(self, script_content):
        """Test that install.ps1 checks if uv is installed."""
        assert "uv --version" in script_content, "install.ps1 should check for uv installation"
        assert "astral.sh/uv/install.ps1" in script_content, "install.ps1 should install uv if missing"

    def test_script_creates_venv(self, script_content):
        """Test that install.ps1 creates virtual environment with uv."""
        assert "uv venv" in script_content, "install.ps1 should create virtual environment with uv"
        assert ".venv\\Scripts\\Activate.ps1" in script_content, "install.ps1 should activate the virtual environment"

    def test_script_installs_package(self, script_content):
        """Test that install.ps1 installs the memcord package."""
        assert "uv pip install -e ." in script_content, "install.ps1 should install memcord in editable mode"

    def test_script_calls_config_generator_with_platform(self, script_content):
        """Test that install.ps1 calls config generator with Windows platform."""
        assert "scripts/generate-config.py" in script_content, "install.ps1 should call generate-config.py"
        assert "--platform windows" in script_content, "install.ps1 should pass --platform windows to config generator"

    def test_script_updates_readme(self, script_content):
        """Test that install.ps1 updates README.md with installation path."""
        assert "README.md" in script_content, "install.ps1 should reference README.md"
        # PowerShell escapes braces in regex patterns, so check for the escaped version
        assert "MEMCORD_PATH" in script_content, "install.ps1 should replace MEMCORD_PATH placeholder"
        assert "-replace" in script_content, "install.ps1 should use -replace for substitution"

    def test_script_shows_next_steps(self, script_content):
        """Test that install.ps1 displays next steps after installation."""
        assert "Next steps:" in script_content, "install.ps1 should show next steps"
        assert "Restart Claude Desktop" in script_content, "install.ps1 should mention restarting Claude Desktop"
        assert "claude mcp list" in script_content, "install.ps1 should mention 'claude mcp list' command"

    def test_script_shows_claude_desktop_config_location(self, script_content):
        """Test that install.ps1 shows Claude Desktop config location."""
        assert "APPDATA" in script_content, "install.ps1 should reference APPDATA for config location"
        assert "Claude\\claude_desktop_config.json" in script_content, (
            "install.ps1 should show Claude Desktop config path"
        )

    def test_script_detects_existing_install(self, script_content):
        """Test that install.ps1 detects an existing checkout and updates it instead of re-cloning."""
        assert '$MODE = "update"' in script_content, "install.ps1 should support an update mode"
        assert "memcord/.git" in script_content, "install.ps1 should detect an existing memcord clone"
        assert "git pull --ff-only" in script_content, "install.ps1 should fast-forward pull on update"

    def test_script_refuses_update_with_local_changes(self, script_content):
        """Test that install.ps1 aborts an update rather than clobbering local modifications."""
        assert "git status --porcelain" in script_content, "install.ps1 should check for local modifications"
        assert "update aborted" in script_content, "install.ps1 should abort the update when local changes exist"

    def test_script_reuses_existing_venv(self, script_content):
        """Test that install.ps1 reuses an existing virtual environment on update."""
        assert 'Test-Path ".venv"' in script_content, (
            "install.ps1 should check for an existing .venv before creating one"
        )

    def test_script_passes_scope_arg_through(self, script_content):
        """Test that install.ps1 accepts and forwards -Scope to generate-config.py."""
        assert "[string]$Scope" in script_content, "install.ps1 should declare a -Scope parameter"
        assert "@scopeArgs" in script_content, "install.ps1 should forward scopeArgs to generate-config.py"

    def test_script_validates_scope_manually_not_via_validateset(self, script_content):
        """Regression test: [ValidateSet] on the $Scope param() breaks the documented
        `irm ... | iex` usage -- Invoke-Expression binds $Scope to an empty string before
        any argument is supplied, and ValidateSet rejects that empty default immediately,
        crashing even the plain no-flags install command. Validation must happen manually
        in the script body instead, where an empty/unset $Scope is accepted (it means
        "let generate-config.py auto-detect")."""
        assert "[ValidateSet(" not in script_content, (
            "install.ps1 must not attach [ValidateSet] to the $Scope param -- it breaks "
            "under `irm ... | iex` (Invoke-Expression binds an empty default before the "
            "attribute is checked, rejecting even the plain no-args install command)"
        )
        assert '-notin @("project", "user")' in script_content, (
            "install.ps1 should validate -Scope manually in the script body instead"
        )

    def test_script_offers_command_picker_on_fresh_install(self, script_content):
        """Test that install.ps1 auto-invokes the command picker on a fresh, interactive install only."""
        assert "IsInputRedirected" in script_content, "install.ps1 should gate the picker on an interactive session"
        assert "--manage-commands" in script_content, "install.ps1 should invoke --manage-commands"
        assert '$MODE -ne "update"' in script_content, (
            "install.ps1 should only auto-invoke the picker on fresh installs"
        )

    def test_script_shows_command_hint_on_update_too(self, script_content):
        """Regression test: update runs must still mention the command picker (a hint, not
        an auto-prompt) -- the whole slash-commands block used to be wrapped in a single
        `$MODE -ne "update"` guard, so update runs got no mention of it at all, not even
        the manual-command hint."""
        assert "choose which memcord-* commands to install globally" in script_content, (
            "install.ps1 should show a hint about --manage-commands on update runs too"
        )


# =============================================================================
# Test scripts/generate-config.py (Configuration Generator) - 15 tests
# =============================================================================


class TestGenerateConfigScript:
    """Tests for the generate-config.py configuration generator."""

    @pytest.fixture
    def script_path(self):
        """Get the path to generate-config.py."""
        return Path("scripts/generate-config.py")

    @pytest.fixture
    def script_content(self, script_path):
        """Load the generate-config.py script content."""
        with open(script_path, encoding="utf-8") as f:
            return f.read()

    def test_script_exists(self, script_path):
        """Test that generate-config.py exists."""
        assert script_path.exists(), "generate-config.py should exist in scripts/"

    def test_script_has_shebang(self, script_content):
        """Test that generate-config.py has proper Python shebang."""
        assert script_content.startswith("#!/usr/bin/env python3"), (
            "generate-config.py should start with #!/usr/bin/env python3"
        )

    def test_script_can_be_imported(self):
        """Test that generate-config.py can be imported as a module."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            assert hasattr(module, "main")
            assert hasattr(module, "get_memcord_path")
            assert hasattr(module, "replace_placeholders")
            assert hasattr(module, "generate_configs")
        finally:
            sys.path.pop(0)

    def test_get_memcord_path_returns_correct_path(self):
        """Test that get_memcord_path returns the correct repository root."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            memcord_path = module.get_memcord_path()
            assert memcord_path.exists()
            assert (memcord_path / "pyproject.toml").exists()
        finally:
            sys.path.pop(0)

    def test_replace_placeholders_unix_paths(self):
        """Test placeholder replacement for Unix paths."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            config = {"path": "{{MEMCORD_PATH}}/src"}
            result = module.replace_placeholders(config, "/home/user/memcord", use_backslashes=False)
            assert result["path"] == "/home/user/memcord/src"
        finally:
            sys.path.pop(0)

    def test_replace_placeholders_windows_paths(self):
        """Test placeholder replacement for Windows paths with backslashes."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            config = {"path": "{{MEMCORD_PATH}}\\src"}
            result = module.replace_placeholders(config, "C:\\Users\\test\\memcord", use_backslashes=True)
            # Windows paths get double-escaped in JSON
            assert "C:\\" in result["path"] or "C:/" in result["path"]
        finally:
            sys.path.pop(0)

    def test_load_template_loads_json(self):
        """Test that load_template correctly loads JSON files."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            template_path = Path("config-templates/vscode/mcp.json")
            if template_path.exists():
                config = module.load_template(template_path)
                assert isinstance(config, dict)
                assert "servers" in config
        finally:
            sys.path.pop(0)

    def test_merge_mcp_servers_preserves_existing(self):
        """Test that merge_mcp_servers preserves existing server configs."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            existing = {"mcpServers": {"other-server": {"command": "other"}}}
            new_servers = {"mcpServers": {"memcord": {"command": "uv"}}}
            result = module.merge_mcp_servers(existing, new_servers)

            assert "other-server" in result["mcpServers"]
            assert "memcord" in result["mcpServers"]
        finally:
            sys.path.pop(0)

    def test_save_config_dry_run_mode(self):
        """Test that save_config respects dry_run mode."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test_config.json"
                config = {"test": "value"}

                # Dry run should not create file
                result = module.save_config(config, output_path, dry_run=True)
                assert result is True
                assert not output_path.exists()
        finally:
            sys.path.pop(0)

    def test_save_config_creates_file(self):
        """Test that save_config creates the config file."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test_config.json"
                config = {"test": "value"}

                result = module.save_config(config, output_path, dry_run=False)
                assert result is True
                assert output_path.exists()

                with open(output_path) as f:
                    saved = json.load(f)
                assert saved == config
        finally:
            sys.path.pop(0)

    def test_save_config_is_atomic_no_tmp_leftover(self):
        """Test that save_config writes via a temp file and leaves no .tmp behind on success."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test_config.json"
                result = module.save_config({"test": "value"}, output_path, dry_run=False)

                assert result is True
                assert output_path.exists()
                assert not output_path.with_name(output_path.name + ".tmp").exists()
        finally:
            sys.path.pop(0)

    def test_save_config_cleans_up_tmp_on_failure(self):
        """Test that a failed write doesn't leave a stray .tmp file or a partial target."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test_config.json"
                # Sets aren't JSON-serializable, so json.dump raises mid-write.
                result = module.save_config({"bad": {1, 2, 3}}, output_path, dry_run=False)

                assert result is False
                assert not output_path.exists()
                assert not output_path.with_name(output_path.name + ".tmp").exists()
        finally:
            sys.path.pop(0)

    def test_get_claude_code_user_config_path_is_home_claude_json(self):
        """Test that the global Claude Code config path is ~/.claude.json."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            assert module.get_claude_code_user_config_path() == Path.home() / ".claude.json"
        finally:
            sys.path.pop(0)

    def test_backup_file_noop_when_source_missing(self):
        """Test that backup_file does nothing if there's no existing file to back up."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                target = Path(tmpdir) / "missing.json"
                module.backup_file(target, dry_run=False)
                assert not target.with_name(target.name + ".bak").exists()
        finally:
            sys.path.pop(0)

    def test_backup_file_creates_backup_of_existing_file(self):
        """Test that backup_file copies the current contents before a merge overwrites them."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                target = Path(tmpdir) / "existing.json"
                target.write_text('{"original": true}', encoding="utf-8")

                module.backup_file(target, dry_run=False)

                backup = target.with_name(target.name + ".bak")
                assert backup.exists()
                assert json.loads(backup.read_text(encoding="utf-8")) == {"original": True}
        finally:
            sys.path.pop(0)

    def test_backup_file_dry_run_does_not_copy(self):
        """Test that backup_file makes no changes in dry-run mode."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with tempfile.TemporaryDirectory() as tmpdir:
                target = Path(tmpdir) / "existing.json"
                target.write_text('{"original": true}', encoding="utf-8")

                module.backup_file(target, dry_run=True)

                assert not target.with_name(target.name + ".bak").exists()
        finally:
            sys.path.pop(0)

    def test_merge_mcp_servers_preserves_unrelated_claude_json_keys(self):
        """Test that merging into a ~/.claude.json-shaped object only touches mcpServers."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            existing = {
                "oauthAccount": {"emailAddress": "user@example.com"},
                "mcpServers": {"other-server": {"command": "other"}},
                "theme": "dark",
                "projects": {"/some/path": {"foo": "bar"}},
            }
            new_servers = {"mcpServers": {"memcord": {"command": "uv"}}}

            result = module.merge_mcp_servers(existing, new_servers)

            assert result["oauthAccount"] == {"emailAddress": "user@example.com"}
            assert result["theme"] == "dark"
            assert result["projects"] == {"/some/path": {"foo": "bar"}}
            assert "other-server" in result["mcpServers"]
            assert "memcord" in result["mcpServers"]
        finally:
            sys.path.pop(0)

    def _isolated_memcord_dir(self, tmp_path: Path) -> Path:
        """Build a throwaway memcord-checkout-shaped dir (real config-templates, nothing else)
        so generate_configs() never writes into this repo's own .vscode/.antigravity/etc."""
        fake_memcord = tmp_path / "memcord"
        shutil.copytree(Path("config-templates"), fake_memcord / "config-templates")
        return fake_memcord

    def _isolated_memcord_dir_with_commands(self, tmp_path: Path) -> Path:
        """Like _isolated_memcord_dir, but also copies the real .claude/commands/ (all
        files, including toon-*.md, to prove the manifest glob excludes it) so command
        tests never read from or write into this repo's real .claude/commands/."""
        fake_memcord = self._isolated_memcord_dir(tmp_path)
        shutil.copytree(Path(".claude/commands"), fake_memcord / ".claude" / "commands")
        return fake_memcord

    def test_generate_configs_user_scope_merges_into_user_config(self, tmp_path, monkeypatch):
        """Test that scope='user' merges memcord into the (monkeypatched) global config path."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            fake_memcord = self._isolated_memcord_dir(tmp_path)
            user_config = tmp_path / "fake_home" / ".claude.json"
            monkeypatch.setattr(module, "get_claude_code_user_config_path", lambda: user_config)

            result = module.generate_configs(
                memcord_path=fake_memcord,
                install_claude_desktop=False,
                install_claude_code=True,
                scope="user",
                dry_run=False,
                verbose=False,
            )

            assert result is True
            assert user_config.exists()
            assert not (fake_memcord / ".mcp.json").exists()
            data = json.loads(user_config.read_text(encoding="utf-8"))
            assert "memcord" in data["mcpServers"]
        finally:
            sys.path.pop(0)

    def test_generate_configs_project_scope_writes_mcp_json(self, tmp_path):
        """Test that scope='project' still writes .mcp.json next to the memcord checkout."""
        sys.path.insert(0, str(Path("scripts")))
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            fake_memcord = self._isolated_memcord_dir(tmp_path)

            result = module.generate_configs(
                memcord_path=fake_memcord,
                install_claude_desktop=False,
                install_claude_code=True,
                scope="project",
                dry_run=False,
                verbose=False,
            )

            assert result is True
            mcp_json = fake_memcord / ".mcp.json"
            assert mcp_json.exists()
            data = json.loads(mcp_json.read_text(encoding="utf-8"))
            assert "memcord" in data["mcpServers"]
        finally:
            sys.path.pop(0)

    def test_platform_detection_variables_exist(self, script_content):
        """Test that platform detection variables are defined."""
        assert "IS_WINDOWS" in script_content
        assert "IS_MACOS" in script_content
        assert "IS_LINUX" in script_content
        assert 'sys.platform == "win32"' in script_content
        assert 'sys.platform == "darwin"' in script_content

    def test_script_has_cli_arguments(self, script_content):
        """Test that the script supports CLI arguments."""
        assert "--install-path" in script_content
        assert "--platform" in script_content
        assert "--dry-run" in script_content
        assert "--quiet" in script_content
        assert "--no-claude-desktop" in script_content
        assert "--no-claude-code" in script_content
        assert "--scope" in script_content
        assert "--manage-commands" in script_content
        assert "--commands" in script_content

    def test_script_handles_all_config_types(self, script_content):
        """Test that the script handles all configuration types."""
        assert "claude-desktop" in script_content
        assert "claude-code" in script_content
        assert "vscode" in script_content
        assert "antigravity" in script_content

    def test_get_claude_desktop_config_path_logic(self, script_content):
        """Test that Claude Desktop config path logic covers all platforms."""
        assert "Library" in script_content  # macOS
        assert "APPDATA" in script_content  # Windows
        assert "XDG_CONFIG_HOME" in script_content  # Linux
        assert ".config" in script_content  # Linux fallback

    def test_script_has_color_output_support(self, script_content):
        """Test that the script supports colored output."""
        assert "ANSI" in script_content or "color" in script_content
        assert "\\033[" in script_content  # ANSI escape codes


# =============================================================================
# Test scripts/generate-config.py -- global slash-command install
# =============================================================================


class TestManageCommands:
    """Tests for the memcord-* slash-command picker (--manage-commands / --commands)."""

    def _load_module(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("generate_config", "scripts/generate-config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _isolated_memcord_dir_with_commands(self, tmp_path: Path) -> Path:
        """Throwaway memcord-checkout-shaped dir with the real .claude/commands/ copied in
        (all files, including toon-*.md, to prove the manifest glob excludes it) -- tests
        never read from or write into this repo's real .claude/commands/."""
        fake_memcord = tmp_path / "memcord"
        shutil.copytree(Path(".claude/commands"), fake_memcord / ".claude" / "commands")
        return fake_memcord

    def test_get_available_commands_excludes_toon_files(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)

            available = module.get_available_commands(fake_memcord)

            names = [p.name for p in available]
            assert len(names) == 17
            assert all(n.startswith("memcord-") for n in names)
            assert not any(n.startswith("toon-") for n in names)
        finally:
            sys.path.pop(0)

    def test_get_user_commands_dir_is_home_claude_commands(self):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            assert module.get_user_commands_dir() == Path.home() / ".claude" / "commands"
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_installs_selected_files(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"

            result = module.apply_command_selection(
                fake_memcord, target_dir, {"memcord-save.md", "memcord-read.md"}, dry_run=False, verbose=False
            )

            assert result is True
            installed = {p.name for p in target_dir.iterdir()}
            assert installed == {"memcord-save.md", "memcord-read.md"}
            source = fake_memcord / ".claude" / "commands" / "memcord-save.md"
            assert (target_dir / "memcord-save.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_ownership_safe_removal(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"
            target_dir.mkdir(parents=True)

            module.apply_command_selection(
                fake_memcord,
                target_dir,
                {"memcord-save.md", "memcord-read.md", "memcord-list.md"},
                dry_run=False,
                verbose=False,
            )
            foreign = target_dir / "memcord-custom-thing.md"
            foreign.write_text("do not touch", encoding="utf-8")

            result = module.apply_command_selection(fake_memcord, target_dir, set(), dry_run=False, verbose=False)

            assert result is True
            remaining = {p.name for p in target_dir.iterdir()}
            assert remaining == {"memcord-custom-thing.md"}
            assert foreign.read_text(encoding="utf-8") == "do not touch"
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_backs_up_edited_file_on_removal(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"

            module.apply_command_selection(fake_memcord, target_dir, {"memcord-save.md"}, dry_run=False, verbose=False)
            installed = target_dir / "memcord-save.md"
            with open(installed, "a", encoding="utf-8") as f:
                f.write("\nuser edit\n")
            edited_content = installed.read_text(encoding="utf-8")

            result = module.apply_command_selection(fake_memcord, target_dir, set(), dry_run=False, verbose=False)

            assert result is True
            assert not installed.exists()
            backup = target_dir / "memcord-save.md.bak"
            assert backup.exists()
            assert backup.read_text(encoding="utf-8") == edited_content
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_deletes_unedited_file_on_removal(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"

            module.apply_command_selection(fake_memcord, target_dir, {"memcord-save.md"}, dry_run=False, verbose=False)
            result = module.apply_command_selection(fake_memcord, target_dir, set(), dry_run=False, verbose=False)

            assert result is True
            assert not (target_dir / "memcord-save.md").exists()
            assert not (target_dir / "memcord-save.md.bak").exists()
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_idempotent_reapply(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"
            selection = {"memcord-save.md", "memcord-read.md"}

            module.apply_command_selection(fake_memcord, target_dir, selection, dry_run=False, verbose=False)
            result = module.apply_command_selection(fake_memcord, target_dir, selection, dry_run=False, verbose=False)

            assert result is True
            assert {p.name for p in target_dir.iterdir()} == selection
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_refreshes_stale_owned_content(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"
            target_dir.mkdir(parents=True)
            (target_dir / "memcord-save.md").write_text("stale content", encoding="utf-8")

            module.apply_command_selection(fake_memcord, target_dir, {"memcord-save.md"}, dry_run=False, verbose=False)

            source = fake_memcord / ".claude" / "commands" / "memcord-save.md"
            assert (target_dir / "memcord-save.md").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        finally:
            sys.path.pop(0)

    def test_apply_command_selection_dry_run_no_op(self, tmp_path):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"

            result = module.apply_command_selection(
                fake_memcord, target_dir, {"memcord-save.md"}, dry_run=True, verbose=False
            )

            assert result is True
            assert not target_dir.exists()
        finally:
            sys.path.pop(0)

    def test_manage_commands_interactive_skips_when_not_tty(self, tmp_path, monkeypatch, capsys):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"
            monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

            result = module.manage_commands_interactive(fake_memcord, target_dir, dry_run=False)

            assert result is True
            assert not target_dir.exists()
            assert "Skipping interactive command picker" in capsys.readouterr().out
        finally:
            sys.path.pop(0)

    def test_manage_commands_interactive_handles_eof(self, tmp_path, monkeypatch, capsys):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            fake_memcord = self._isolated_memcord_dir_with_commands(tmp_path)
            target_dir = tmp_path / "fake_home" / ".claude" / "commands"
            monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

            def raise_eof(*args, **kwargs):
                raise EOFError

            monkeypatch.setattr("builtins.input", raise_eof)

            result = module.manage_commands_interactive(fake_memcord, target_dir, dry_run=False)

            assert result is True
            assert not target_dir.exists()
            assert "Cancelled" in capsys.readouterr().out
        finally:
            sys.path.pop(0)

    def test_parse_commands_arg_all_none_and_explicit_list(self):
        sys.path.insert(0, str(Path("scripts")))
        try:
            module = self._load_module()
            available = ["memcord-save.md", "memcord-read.md", "memcord-list.md"]

            assert module.parse_commands_arg("all", available) == set(available)
            assert module.parse_commands_arg("none", available) == set()
            assert module.parse_commands_arg("memcord-save,memcord-read.md", available) == {
                "memcord-save.md",
                "memcord-read.md",
            }
            with pytest.raises(ValueError):
                module.parse_commands_arg("not-a-real-command", available)
        finally:
            sys.path.pop(0)


# =============================================================================
# Test Config Templates Existence and Validity - 10 tests
# =============================================================================


class TestConfigTemplates:
    """Tests for configuration template files."""

    def test_config_templates_directory_exists(self):
        """Test that config-templates directory exists."""
        assert Path("config-templates").exists()
        assert Path("config-templates").is_dir()

    def test_vscode_template_exists(self):
        """Test that VSCode template exists."""
        assert Path("config-templates/vscode/mcp.json").exists()

    def test_claude_code_template_exists(self):
        """Test that Claude Code templates exist."""
        assert Path("config-templates/claude-code/mcp.json").exists()
        assert Path("config-templates/claude-code/mcp.windows.json").exists()

    def test_claude_desktop_template_exists(self):
        """Test that Claude Desktop templates exist."""
        assert Path("config-templates/claude-desktop/config.json").exists()
        assert Path("config-templates/claude-desktop/config.windows.json").exists()

    def test_antigravity_template_exists(self):
        """Test that Antigravity template exists."""
        assert Path("config-templates/antigravity/mcp_config.json").exists()

    def test_vscode_template_valid_json(self):
        """Test that VSCode template is valid JSON."""
        with open("config-templates/vscode/mcp.json") as f:
            config = json.load(f)
        assert "servers" in config

    def test_claude_code_template_valid_json(self):
        """Test that Claude Code template is valid JSON."""
        with open("config-templates/claude-code/mcp.json") as f:
            config = json.load(f)
        assert "mcpServers" in config

    def test_claude_desktop_template_valid_json(self):
        """Test that Claude Desktop template is valid JSON."""
        with open("config-templates/claude-desktop/config.json") as f:
            config = json.load(f)
        assert "mcpServers" in config

    def test_templates_have_memcord_server(self):
        """Test that all templates define memcord server."""
        templates = [
            ("config-templates/vscode/mcp.json", "servers"),
            ("config-templates/claude-code/mcp.json", "mcpServers"),
            ("config-templates/claude-desktop/config.json", "mcpServers"),
        ]

        for template_path, servers_key in templates:
            with open(template_path) as f:
                config = json.load(f)
            assert "memcord" in config[servers_key], f"Template {template_path} should define memcord server"

    def test_templates_use_uv_command(self):
        """Test that all templates use uv as the command."""
        templates = [
            ("config-templates/vscode/mcp.json", "servers"),
            ("config-templates/claude-code/mcp.json", "mcpServers"),
            ("config-templates/claude-desktop/config.json", "mcpServers"),
        ]

        for template_path, servers_key in templates:
            with open(template_path) as f:
                config = json.load(f)
            assert config[servers_key]["memcord"]["command"] == "uv", (
                f"Template {template_path} should use 'uv' command"
            )


# =============================================================================
# Test utilities/protect_data.py
# =============================================================================


class TestProtectDataDetection:
    """Tests for detect_memory_data() slot-file filtering."""

    def _load_protect_data(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("protect_data", "utilities/protect_data.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_excludes_storage_links_registry_and_config_sidecars(self, tmp_path):
        """_storage_links.json and *_config.json sidecars are not real slots."""
        memory_dir = tmp_path / "memory_slots"
        memory_dir.mkdir()
        (memory_dir / "myslot.json").write_text("{}")
        (memory_dir / "myslot_config.json").write_text("{}")
        (memory_dir / "_storage_links.json").write_text("{}")
        (memory_dir / "backup_metadata.json").write_text("{}")

        protect_data = self._load_protect_data()
        data_exists, slot_count, _total_size, slot_names = protect_data.detect_memory_data(str(memory_dir))

        assert data_exists is True
        assert slot_count == 1
        assert slot_names == ["myslot"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
