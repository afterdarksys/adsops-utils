#!/bin/bash
#
# AfterCloud Tools Setup Script
#
# Sets up Python environment and installs Oracle Cloud management tools.
# Designed for accessibility - uses clear text output.
#
# Usage:
#   ./setup.sh              # Full setup
#   ./setup.sh --check      # Check prerequisites only
#   ./setup.sh --venv       # Create virtualenv only
#   ./setup.sh --install    # Install dependencies only
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Colors disabled for screen reader compatibility
# Set TERM=dumb or use --no-color for plain output

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

log_plain() {
    echo "$1"
}

error() {
    echo "[ERROR] $1" >&2
}

check_prerequisites() {
    log "Checking prerequisites..."

    local missing=0

    # Check Python 3
    if command -v python3 &> /dev/null; then
        local py_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_plain "  Python 3: Found (version $py_version)"
    else
        error "  Python 3: Not found"
        log_plain "  Install Python 3.8 or later from https://python.org"
        missing=1
    fi

    # Check pip
    if python3 -m pip --version &> /dev/null; then
        log_plain "  pip: Found"
    else
        error "  pip: Not found"
        log_plain "  Install with: python3 -m ensurepip"
        missing=1
    fi

    # Check OCI CLI (optional but recommended)
    if command -v oci &> /dev/null; then
        log_plain "  OCI CLI: Found"
    else
        log_plain "  OCI CLI: Not found (optional)"
        log_plain "  Install from: https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm"
    fi

    # Check OCI config
    if [ -f "$HOME/.oci/config" ]; then
        log_plain "  OCI config: Found at ~/.oci/config"
    else
        log_plain "  OCI config: Not found"
        log_plain "  Run 'oci setup config' to create it"
    fi

    # Check SSH key
    if [ -f "$HOME/.ssh/id_rsa.pub" ] || [ -f "$HOME/.ssh/id_ed25519.pub" ]; then
        log_plain "  SSH key: Found"
    else
        log_plain "  SSH key: Not found"
        log_plain "  Generate with: ssh-keygen -t ed25519"
    fi

    return $missing
}

create_venv() {
    log "Creating Python virtual environment..."

    if [ -d "$VENV_DIR" ]; then
        log_plain "  Virtual environment already exists at: $VENV_DIR"
        read -p "  Remove and recreate? (y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            rm -rf "$VENV_DIR"
        else
            return 0
        fi
    fi

    python3 -m venv "$VENV_DIR"
    log_plain "  Created virtual environment at: $VENV_DIR"

    # Activate
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    log "Upgrading pip..."
    pip install --upgrade pip --quiet

    log_plain "  Virtual environment ready"
}

install_dependencies() {
    log "Installing dependencies..."

    # Activate venv if exists
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi

    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements.txt"
        log_plain "  Dependencies installed successfully"
    else
        error "requirements.txt not found"
        return 1
    fi
}

make_executable() {
    log "Making scripts executable..."

    local scripts=(
        "orcvm.py"
        "orccont.py"
        "generate_terraform.py"
        "generate_ansible.py"
        "blockutil.py"
        "ticketutil.py"
        "orckms.py"
        "mkocicmd.py"
        "cloudtop.py"
        "oci_free_instance.py"
    )

    for script in "${scripts[@]}"; do
        if [ -f "$SCRIPT_DIR/$script" ]; then
            chmod +x "$SCRIPT_DIR/$script"
            log_plain "  Made executable: $script"
        fi
    done
}

create_symlinks() {
    log "Creating command shortcuts..."

    local bin_dir="$HOME/.local/bin"

    if [ ! -d "$bin_dir" ]; then
        mkdir -p "$bin_dir"
        log_plain "  Created $bin_dir"
    fi

    # Check if bin_dir is in PATH
    if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
        log_plain ""
        log_plain "  Note: $bin_dir is not in your PATH"
        log_plain "  Add this to your ~/.bashrc or ~/.zshrc:"
        log_plain "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        log_plain ""
    fi

    local scripts=(
        "orcvm:orcvm.py"
        "orccont:orccont.py"
        "generate-terraform:generate_terraform.py"
        "generate-ansible:generate_ansible.py"
        "blockutil:blockutil.py"
        "ticketutil:ticketutil.py"
        "orckms:orckms.py"
        "mkocicmd:mkocicmd.py"
        "cloudtop:cloudtop.py"
        "oci-free-instance:oci_free_instance.py"
    )

    for item in "${scripts[@]}"; do
        local name="${item%%:*}"
        local script="${item##*:}"

        if [ -f "$SCRIPT_DIR/$script" ]; then
            # Create wrapper script that activates venv
            cat > "$bin_dir/$name" << EOF
#!/bin/bash
# AfterCloud wrapper script
source "$VENV_DIR/bin/activate" 2>/dev/null || true
exec python3 "$SCRIPT_DIR/$script" "\$@"
EOF
            chmod +x "$bin_dir/$name"
            log_plain "  Created command: $name"
        fi
    done
}

print_usage() {
    log_plain ""
    log_plain "AfterCloud Tools - Setup Complete"
    log_plain "=" * 50
    log_plain ""
    log_plain "Available commands:"
    log_plain "  orcvm            - VM management"
    log_plain "  orccont          - Container management"
    log_plain "  blockutil        - Block storage"
    log_plain "  orckms           - Secrets/Vault management"
    log_plain "  generate-terraform - Export to Terraform"
    log_plain "  generate-ansible   - Export to Ansible"
    log_plain "  ticketutil       - Change ticket client"
    log_plain "  mkocicmd         - OCI command generator"
    log_plain "  cloudtop         - Multi-cloud monitor"
    log_plain "  oci-free-instance - Free tier instance retry"
    log_plain ""
    log_plain "Quick start:"
    log_plain "  1. Configure OCI: oci setup config"
    log_plain "  2. List VMs: orcvm list"
    log_plain "  3. Get help: orcvm --help"
    log_plain ""
    log_plain "For screen reader users:"
    log_plain "  All commands output plain text with timestamps."
    log_plain "  Use --help flag for detailed usage instructions."
    log_plain ""
}

main() {
    log_plain ""
    log_plain "AfterCloud Tools Setup"
    log_plain "Oracle Cloud Management for AWS Migrants"
    log_plain "=" * 50
    log_plain ""

    case "${1:-}" in
        --check)
            check_prerequisites
            ;;
        --venv)
            create_venv
            ;;
        --install)
            install_dependencies
            ;;
        *)
            # Full setup
            if ! check_prerequisites; then
                error "Prerequisites not met. Fix the issues above and try again."
                exit 1
            fi

            log_plain ""
            create_venv
            install_dependencies
            make_executable
            create_symlinks
            print_usage
            ;;
    esac
}

main "$@"
