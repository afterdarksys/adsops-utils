#!/usr/bin/env python3
"""
opsctl.py - OCI Operations Controller
After Dark Systems - Ops Utils

Unified CLI for OCI infrastructure operations including:
- Bastion session management
- OS Management operations
- Patch management
- Secrets management (OCI Vault)
- Terraform state management
- Backend service connections

Usage:
    ./opsctl.py <module> <command> [args...]
    ./opsctl.py --env prod bastion list-sessions

Modules:
    bastion      - OCI Bastion session management
    osm          - OS Management session & agent operations
    patch        - Patch management operations
    secrets      - OCI Vault secrets management
    state        - Terraform state management
    os-mgmt      - OS Management service operations
    jump         - Jump host access
    backend      - Backend service connections
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


# Find the config file and scripts directory
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "config.json"
PYTHON_SCRIPTS_DIR = SCRIPT_DIR / "scripts" / "python"
BASH_SCRIPTS_DIR = SCRIPT_DIR / "scripts" / "bash"


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


def log_info(message: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")


def log_success(message: str) -> None:
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def log_warn(message: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {message}")


def log_error(message: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}", file=sys.stderr)


def load_config() -> dict[str, Any]:
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        log_warn(f"Config file not found: {CONFIG_FILE}")
        return {}

    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log_error(f"Failed to parse config file: {e}")
        return {}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    log_success(f"Config saved to: {CONFIG_FILE}")


def apply_environment(config: dict, env_name: str) -> dict:
    """Apply environment-specific configuration overrides."""
    environments = config.get("environments", {})
    if env_name in environments:
        env_config = environments[env_name]
        # Merge environment config into OCI config
        for key, value in env_config.items():
            if value:  # Only override if value is set
                config.setdefault("oci", {})[key] = value
        log_info(f"Using environment: {env_name}")
    else:
        log_warn(f"Environment '{env_name}' not found in config")
    return config


def set_environment_vars(config: dict) -> None:
    """Set environment variables from config."""
    oci_config = config.get("oci", {})
    ssh_config = config.get("ssh", {})
    tf_config = config.get("terraform", {})
    session_config = config.get("sessions", {})

    env_mapping = {
        "OCI_PROFILE": oci_config.get("profile"),
        "COMPARTMENT_OCID": oci_config.get("compartment_ocid"),
        "BASTION_OCID": oci_config.get("bastion_ocid"),
        "VAULT_OCID": oci_config.get("vault_ocid"),
        "KEY_OCID": oci_config.get("key_ocid"),
        "NAMESPACE": oci_config.get("namespace"),
        "SSH_KEY": ssh_config.get("key_path"),
        "DEFAULT_USER": ssh_config.get("default_user"),
        "STATE_BUCKET": tf_config.get("state_bucket"),
        "LOCK_BUCKET": tf_config.get("lock_bucket"),
        "DEFAULT_TTL": str(session_config.get("default_ttl", 10800)),
        "TUNNEL_DIR": session_config.get("tunnel_dir"),
    }

    for key, value in env_mapping.items():
        if value:
            os.environ[key] = value


# Module mappings
MODULES = {
    "bastion": {
        "python": "bastion.py",
        "bash": "bastion.sh",
        "description": "OCI Bastion session management"
    },
    "osm": {
        "python": "osm_session.py",
        "bash": "osm-session.sh",
        "description": "OS Management session & agent operations"
    },
    "patch": {
        "python": "patch_management.py",
        "bash": "patch-management.sh",
        "description": "Patch management operations"
    },
    "secrets": {
        "python": "parameter_store.py",
        "bash": "parameter-store.sh",
        "description": "OCI Vault secrets management"
    },
    "state": {
        "python": "state_management.py",
        "bash": "state-management.sh",
        "description": "Terraform state management"
    },
    "os-mgmt": {
        "python": "os_management.py",
        "bash": "os-management.sh",
        "description": "OS Management service operations"
    },
    "jump": {
        "python": "jump_host.py",
        "bash": "jump-host.sh",
        "description": "Jump host access"
    },
    "backend": {
        "python": "backend_sessions.py",
        "bash": "backend-sessions.sh",
        "description": "Backend service connections"
    }
}


def run_module(
    module: str,
    command: str,
    args: list[str],
    use_bash: bool = False
) -> int:
    """Run a module command."""
    if module not in MODULES:
        log_error(f"Unknown module: {module}")
        log_info(f"Available modules: {', '.join(MODULES.keys())}")
        return 1

    module_info = MODULES[module]

    if use_bash:
        script_path = BASH_SCRIPTS_DIR / module_info["bash"]
        cmd = [str(script_path), command] + args
    else:
        script_path = PYTHON_SCRIPTS_DIR / module_info["python"]
        cmd = [sys.executable, str(script_path), command] + args

    if not script_path.exists():
        log_error(f"Script not found: {script_path}")
        return 1

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        log_error(f"Failed to run command: {e}")
        return 1


def cmd_config(args: argparse.Namespace) -> int:
    """Handle config subcommand."""
    config = load_config()

    if args.config_command == "show":
        print(json.dumps(config, indent=2))
    elif args.config_command == "set":
        # Parse key path (e.g., "oci.profile" or "ssh.key_path")
        keys = args.key.split(".")
        current = config
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = args.value
        save_config(config)
    elif args.config_command == "get":
        keys = args.key.split(".")
        current = config
        for key in keys:
            current = current.get(key, {})
        if current:
            if isinstance(current, dict):
                print(json.dumps(current, indent=2))
            else:
                print(current)
        else:
            log_error(f"Key not found: {args.key}")
            return 1
    elif args.config_command == "env":
        if args.env_name:
            # Show specific environment
            envs = config.get("environments", {})
            if args.env_name in envs:
                print(json.dumps(envs[args.env_name], indent=2))
            else:
                log_error(f"Environment not found: {args.env_name}")
                return 1
        else:
            # List environments
            envs = config.get("environments", {})
            for name in envs:
                print(name)

    return 0


def cmd_list_modules(args: argparse.Namespace) -> int:
    """List available modules."""
    print(f"\n{Colors.BOLD}Available Modules:{Colors.NC}\n")
    for name, info in MODULES.items():
        print(f"  {Colors.CYAN}{name:12}{Colors.NC}  {info['description']}")
    print()
    return 0


def cmd_help_module(args: argparse.Namespace) -> int:
    """Show help for a specific module."""
    module = args.module
    if module not in MODULES:
        log_error(f"Unknown module: {module}")
        return 1

    # Run the module's help
    return run_module(module, "--help", [], use_bash=args.bash)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OCI Operations Controller - Unified CLI for OCI infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s bastion list-sessions
  %(prog)s --env prod secrets get ocid1.vaultsecret...
  %(prog)s backend connect-postgres 10.0.1.5 5432 mydb admin
  %(prog)s config set oci.compartment_ocid ocid1.compartment...
  %(prog)s modules

Environment Variables:
  OPSCTL_ENV         Default environment to use
  OPSCTL_USE_BASH    Use bash scripts instead of Python (set to 1)
"""
    )

    parser.add_argument(
        "--env", "-e",
        help="Environment to use (dev, staging, prod)",
        default=os.environ.get("OPSCTL_ENV")
    )
    parser.add_argument(
        "--bash", "-b",
        action="store_true",
        help="Use bash scripts instead of Python",
        default=os.environ.get("OPSCTL_USE_BASH") == "1"
    )
    parser.add_argument(
        "--config-file", "-c",
        help="Path to config file",
        default=str(CONFIG_FILE)
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_command")

    config_show = config_sub.add_parser("show", help="Show current config")
    config_set = config_sub.add_parser("set", help="Set config value")
    config_set.add_argument("key", help="Config key (e.g., oci.profile)")
    config_set.add_argument("value", help="Value to set")
    config_get = config_sub.add_parser("get", help="Get config value")
    config_get.add_argument("key", help="Config key")
    config_env = config_sub.add_parser("env", help="List/show environments")
    config_env.add_argument("env_name", nargs="?", help="Environment name")

    # Modules subcommand
    subparsers.add_parser("modules", help="List available modules")

    # Help for specific module
    help_parser = subparsers.add_parser("help", help="Show help for a module")
    help_parser.add_argument("module", help="Module name")

    # Parse known args first to handle module commands
    args, remaining = parser.parse_known_args()

    # Load and apply config
    global CONFIG_FILE
    if args.config_file:
        CONFIG_FILE = Path(args.config_file)

    config = load_config()

    if args.env:
        config = apply_environment(config, args.env)

    set_environment_vars(config)

    # Handle subcommands
    if args.subcommand == "config":
        return cmd_config(args)
    elif args.subcommand == "modules":
        return cmd_list_modules(args)
    elif args.subcommand == "help":
        return cmd_help_module(args)
    elif args.subcommand in MODULES:
        # Module command
        if remaining:
            command = remaining[0]
            module_args = remaining[1:]
        else:
            command = "--help"
            module_args = []
        return run_module(args.subcommand, command, module_args, use_bash=args.bash)
    elif args.subcommand:
        log_error(f"Unknown subcommand: {args.subcommand}")
        parser.print_help()
        return 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
