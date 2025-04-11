#!/usr/bin/env python3

import json
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Configuration Data ---

# Define the specific server entry we want to install/update
SERVER_NAME = "simple-telegram-mcp"
SERVER_ENTRY = {
    "command": "uvx",  # Use uvx as the command
    "args": ["simple-telegram-mcp"],
}

# Configuration details for supported clients
MCP_CLIENT_CONFIG: Dict[str, Dict[str, Any]] = {
    "vscode": {
        "name": "Visual Studio Code",
        "paths": {
            "windows": "%APPDATA%\\Code\\User\\settings.json",
            "osx": "~/Library/Application Support/Code/User/settings.json",
            "linux": "~/.config/Code/User/settings.json",
        },
        "json_path": ["mcp", "servers"],  # Represents $.mcp.servers
    },
    "vscode-insiders": {
        "name": "Visual Studio Code Insiders",
        "paths": {
            "windows": "%APPDATA%\\Code - Insiders\\User\\settings.json",
            "osx": "~/Library/Application Support/Code - Insiders/User/settings.json",
            "linux": "~/.config/Code - Insiders/User/settings.json",
        },
        "json_path": ["mcp", "servers"],  # Represents $.mcp.servers
    },
    "windsurf": {
        "name": "Windsurf",
        "paths": {
            "windows": "%USERPROFILE%\\.codeium\\windsurf\\mcp_config.json",
            "osx": "~/.codeium/windsurf/mcp_config.json",
            "linux": "~/.codeium/windsurf/mcp_config.json",
        },
        "json_path": ["mcpServers"],  # Represents $.mcpServers
    },
    "cursor": {
        "name": "Cursor",
        "paths": {
            "windows": "%USERPROFILE%\\.cursor\\mcp.json",
            "osx": "~/.cursor/mcp.json",
            "linux": "~/.cursor/mcp.json",
        },
        "json_path": ["mcpServers"],  # Represents $.mcpServers
    },
    "claude-desktop": {
        "name": "Claude Desktop",
        "paths": {
            "windows": "%APPDATA%\\Claude\\claude_desktop_config.json",
            "osx": "~/Library/Application Support/Claude/claude_desktop_config.json",
            "linux": "~/.config/Claude/claude_desktop_config.json",
        },
        "json_path": ["mcpServers"],  # Represents $.mcpServers
    },
    "claude-code": {
        "name": "Claude Code",
        "paths": {
            "windows": "%USERPROFILE%\\.claude.json",
            "osx": "~/.claude.json",
            "linux": "~/.claude.json",
        },
        "json_path": ["mcpServers"],  # Represents $.mcpServers
    },
}

# --- Helper Functions ---


def get_os_type() -> str:
    """Detects the operating system."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "osx"
    elif system == "linux":
        return "linux"
    else:
        print(
            f"Error: Unsupported operating system '{platform.system()}'",
            file=sys.stderr,
        )
        sys.exit(1)


def resolve_path(path_str: str) -> Path:
    """Resolves environment variables and ~ in paths."""
    # Expand environment variables first (e.g., %APPDATA%)
    expanded_vars = os.path.expandvars(path_str)
    # Expand user home directory (~)
    path = Path(expanded_vars).expanduser()
    # Return absolute path
    try:
        return path.resolve()
    except FileNotFoundError:
        # If the path doesn't exist yet, resolve() might fail.
        # Return the expanded path directly in this case.
        # The directory creation logic will handle non-existent dirs later.
        return path
    except Exception as e:
        print(f"Error resolving path '{path_str}': {e}", file=sys.stderr)
        sys.exit(1)


def load_json_config(file_path: Path) -> Dict[str, Any]:
    """Loads JSON data from a file, returning {} if file not found or empty."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return {}  # Handle empty file
            return json.loads(content)
    except FileNotFoundError:
        return {}  # File doesn't exist, start with empty config
    except json.JSONDecodeError:
        print(
            f"Error: Invalid JSON found in '{file_path}'. Please fix or remove the file.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error reading configuration file '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


def save_json_config(file_path: Path, data: Dict[str, Any]) -> None:
    """Saves JSON data to a file atomically."""
    temp_path: Optional[Path] = None
    try:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file then rename for atomicity
        # Use delete=False because we will rename it manually
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=file_path.name + ".",
            delete=False,
        ) as temp_f:
            temp_path = Path(temp_f.name)
            json.dump(data, temp_f, indent=4)  # Use indent for readability

        # Ensure the temp file is properly closed before renaming
        # (already handled by 'with' statement)

        # Atomic rename (or best effort on some systems)
        os.replace(temp_path, file_path)

    except PermissionError:
        print(
            f"Error: Permission denied writing to '{file_path}'. Check directory permissions.",
            file=sys.stderr,
        )
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)  # Clean up temp file
        sys.exit(1)
    except Exception as e:
        print(f"Error writing configuration file '{file_path}': {e}", file=sys.stderr)
        # Clean up temp file if rename failed
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        sys.exit(1)


def navigate_and_set(
    data: Dict[str, Any],
    path_keys: List[str],
    server_name: str,
    server_config: Dict[str, Any],
) -> bool:
    """
    Navigates dict using path_keys, sets server_config at server_name.
    Returns True if changes were made, False otherwise (idempotency).
    """
    current_level = data
    try:
        for key in path_keys:
            # Ensure the current level is a dictionary before proceeding
            if not isinstance(current_level, dict):
                print(
                    f"Error: Configuration structure conflict. Expected a dictionary at path segment leading to '{key}', but found type '{type(current_level).__name__}'.",
                    file=sys.stderr,
                )
                # Attempt to recover if possible, e.g., overwrite if it's not critical?
                # For safety, let's error out. User needs to fix their config.
                # Alternatively, could try to replace the non-dict item, but that's risky.
                # Example recovery (use with caution):
                # parent_level[parent_key] = {} # Overwrite the non-dict item
                # current_level = parent_level[parent_key]
                # current_level = current_level.setdefault(key, {})
                print(
                    "Please check your configuration file structure.", file=sys.stderr
                )
                sys.exit(1)

            current_level = current_level.setdefault(key, {})

        # Final check after loop - current_level should be the target dict
        if not isinstance(current_level, dict):
            print(
                f"Error: Configuration structure conflict. Expected the final target path '{'.'.join(path_keys)}' to be a dictionary, but found type '{type(current_level).__name__}'.",
                file=sys.stderr,
            )
            print("Please check your configuration file structure.", file=sys.stderr)
            sys.exit(1)

    except TypeError as e:
        print(
            f"Error navigating configuration structure: {e}. Key path: {path_keys}",
            file=sys.stderr,
        )
        print(
            "This might indicate an unexpected data type (e.g., a list instead of a dictionary) in your configuration file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check for existing server entry (Idempotency)
    existing_server = current_level.get(server_name)

    # Deep comparison of the server entry content
    if existing_server == server_config:
        print(
            f"MCP server '{server_name}' with the exact same configuration already exists. No changes made."
        )
        return False  # Indicate no changes were made
    elif existing_server is not None:
        print(f"Updating existing MCP server '{server_name}' with new configuration.")
        current_level[server_name] = server_config
        return True  # Indicate changes were made
    else:
        print(f"Adding new MCP server '{server_name}'.")
        current_level[server_name] = server_config
        return True  # Indicate changes were made


# --- Main Installation Function ---


def install_mcp_server(client_key: str) -> None:
    """Installs or updates the MCP server config for the specified client."""
    client_config = MCP_CLIENT_CONFIG.get(client_key)
    if not client_config:
        print(f"Error: Invalid client key '{client_key}' provided.", file=sys.stderr)
        sys.exit(1)

    client_name = client_config["name"]
    print(f"Attempting to install configuration for: {client_name}")

    # --- Handle Claude Code Caveat ---
    if client_key == "claude-code":
        print("\n--- WARNING for Claude Code ---", file=sys.stderr)
        print(
            "Modifying ~/.claude.json directly is not the documented method for configuring Claude Code MCP servers.",
            file=sys.stderr,
        )
        print(
            "The official method likely involves the 'claude mcp' CLI command.",
            file=sys.stderr,
        )
        print(
            "This script will proceed as requested, but the configuration might be ignored or overwritten by the application.",
            file=sys.stderr,
        )
        print("-----------------------------\n", file=sys.stderr)
        # Consider adding a confirmation prompt here in a real-world scenario

    # --- Determine OS and Path ---
    os_type = get_os_type()
    config_path_str = client_config["paths"].get(os_type)
    if not config_path_str:
        print(
            f"Error: No configuration path defined for {client_name} on {os_type.upper()}",
            file=sys.stderr,
        )
        sys.exit(1)

    config_file_path = resolve_path(config_path_str)
    print(f"Target configuration file: {config_file_path}")

    # --- Load Existing Config ---
    config_data = load_json_config(config_file_path)

    # --- Prepare New Server Entry ---
    json_path_keys = client_config["json_path"]

    # --- Add/Update Server Entry ---
    made_changes = navigate_and_set(
        config_data, json_path_keys, SERVER_NAME, SERVER_ENTRY
    )

    # --- Save Config (only if changes were made) ---
    if made_changes:
        save_json_config(config_file_path, config_data)
        print(
            f"Configuration file '{config_file_path}' updated successfully for {client_name}."
        )
    else:
        # Message already printed by navigate_and_set if no changes needed
        pass

    print("Installation process completed.")


# Example of how to call this if run directly (for testing)
# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         install_mcp_server(sys.argv[1])
#     else:
#         print("Usage: python install.py <client_key>")
#         print("Available keys:", list(MCP_CLIENT_CONFIG.keys()))
