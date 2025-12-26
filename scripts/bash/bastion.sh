#!/bin/bash
#
# bastion.sh - OCI Bastion Service Operations Wrapper
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for OCI Bastion service operations
# including session management, SSH tunneling, and port forwarding.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
BASTION_OCID="${BASTION_OCID:-}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"
DEFAULT_TTL="${DEFAULT_TTL:-10800}"  # 3 hours in seconds

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Check required dependencies
check_dependencies() {
    local missing=()
    for cmd in oci jq; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required dependencies: ${missing[*]}"
        exit 1
    fi
}

# Validate OCI configuration
validate_oci_config() {
    if ! oci session validate --profile "$OCI_PROFILE" &>/dev/null 2>&1; then
        if ! oci iam region list --profile "$OCI_PROFILE" &>/dev/null 2>&1; then
            log_error "OCI CLI not configured or session expired. Run 'oci session authenticate' or check your config."
            exit 1
        fi
    fi
}

# List all bastions in compartment
list_bastions() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required. Set COMPARTMENT_OCID or pass as argument."
        exit 1
    fi

    log_info "Listing bastions in compartment..."
    oci bastion bastion list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(.name)\t\(."lifecycle-state")"'
}

# Get bastion details
get_bastion() {
    local bastion_id="${1:-$BASTION_OCID}"

    if [[ -z "$bastion_id" ]]; then
        log_error "Bastion OCID required. Set BASTION_OCID or pass as argument."
        exit 1
    fi

    oci bastion bastion get \
        --bastion-id "$bastion_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# List active sessions for a bastion
list_sessions() {
    local bastion_id="${1:-$BASTION_OCID}"
    local state="${2:-ACTIVE}"

    if [[ -z "$bastion_id" ]]; then
        log_error "Bastion OCID required."
        exit 1
    fi

    log_info "Listing $state sessions..."
    oci bastion session list \
        --bastion-id "$bastion_id" \
        --session-lifecycle-state "$state" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."session-type")\t\(."lifecycle-state")"'
}

# Create SSH port forwarding session
create_port_forward_session() {
    local bastion_id="${1:-$BASTION_OCID}"
    local target_host="$2"
    local target_port="$3"
    local session_name="${4:-port-forward-$(date +%s)}"
    local ttl="${5:-$DEFAULT_TTL}"
    local ssh_pub_key="${6:-$HOME/.ssh/id_rsa.pub}"

    if [[ -z "$bastion_id" || -z "$target_host" || -z "$target_port" ]]; then
        log_error "Usage: create_port_forward_session <bastion_id> <target_host> <target_port> [session_name] [ttl] [ssh_pub_key]"
        exit 1
    fi

    if [[ ! -f "$ssh_pub_key" ]]; then
        log_error "SSH public key not found: $ssh_pub_key"
        exit 1
    fi

    local pub_key_content
    pub_key_content=$(cat "$ssh_pub_key")

    log_info "Creating port forwarding session to ${target_host}:${target_port}..."

    oci bastion session create-port-forwarding \
        --bastion-id "$bastion_id" \
        --display-name "$session_name" \
        --ssh-public-key-file "$ssh_pub_key" \
        --target-private-ip "$target_host" \
        --target-port "$target_port" \
        --session-ttl "$ttl" \
        --profile "$OCI_PROFILE" \
        --wait-for-state ACTIVE \
        --output json | jq '.data'
}

# Create managed SSH session (to compute instance)
create_managed_ssh_session() {
    local bastion_id="${1:-$BASTION_OCID}"
    local instance_id="$2"
    local target_user="${3:-opc}"
    local session_name="${4:-ssh-session-$(date +%s)}"
    local ttl="${5:-$DEFAULT_TTL}"
    local ssh_pub_key="${6:-$HOME/.ssh/id_rsa.pub}"

    if [[ -z "$bastion_id" || -z "$instance_id" ]]; then
        log_error "Usage: create_managed_ssh_session <bastion_id> <instance_id> [target_user] [session_name] [ttl] [ssh_pub_key]"
        exit 1
    fi

    if [[ ! -f "$ssh_pub_key" ]]; then
        log_error "SSH public key not found: $ssh_pub_key"
        exit 1
    fi

    log_info "Creating managed SSH session to instance ${instance_id}..."

    oci bastion session create-managed-ssh \
        --bastion-id "$bastion_id" \
        --display-name "$session_name" \
        --ssh-public-key-file "$ssh_pub_key" \
        --target-resource-id "$instance_id" \
        --target-os-username "$target_user" \
        --session-ttl "$ttl" \
        --profile "$OCI_PROFILE" \
        --wait-for-state ACTIVE \
        --output json | jq '.data'
}

# Get session details and connection command
get_session() {
    local session_id="$1"

    if [[ -z "$session_id" ]]; then
        log_error "Session OCID required."
        exit 1
    fi

    local session_data
    session_data=$(oci bastion session get \
        --session-id "$session_id" \
        --profile "$OCI_PROFILE" \
        --output json)

    echo "$session_data" | jq '.data'

    # Extract and display connection command
    local ssh_metadata
    ssh_metadata=$(echo "$session_data" | jq -r '.data["ssh-metadata"] // empty')

    if [[ -n "$ssh_metadata" ]]; then
        echo ""
        log_info "Connection command:"
        echo "$ssh_metadata" | jq -r '.command // empty'
    fi
}

# Connect to a session (generates SSH command)
connect_session() {
    local session_id="$1"
    local local_port="${2:-}"
    local ssh_key="${3:-$HOME/.ssh/id_rsa}"

    if [[ -z "$session_id" ]]; then
        log_error "Session OCID required."
        exit 1
    fi

    local session_data
    session_data=$(oci bastion session get \
        --session-id "$session_id" \
        --profile "$OCI_PROFILE" \
        --output json)

    local session_type
    session_type=$(echo "$session_data" | jq -r '.data["session-type"]')

    local bastion_user
    bastion_user=$(echo "$session_data" | jq -r '.data["bastion-user-name"]')

    local bastion_host
    bastion_host=$(echo "$session_data" | jq -r '.data["bastion-public-host-key-info"]["public-host-key"]' | cut -d' ' -f1-2)

    # Get the bastion endpoint
    local bastion_id
    bastion_id=$(echo "$session_data" | jq -r '.data["bastion-id"]')

    local bastion_info
    bastion_info=$(oci bastion bastion get --bastion-id "$bastion_id" --profile "$OCI_PROFILE" --output json)

    local bastion_endpoint
    bastion_endpoint=$(echo "$bastion_info" | jq -r '.data["bastion-public-host-key-info"]["public-host-key"]' 2>/dev/null || echo "")

    if [[ "$session_type" == "PORT_FORWARDING" ]]; then
        local target_ip target_port
        target_ip=$(echo "$session_data" | jq -r '.data["target-resource-details"]["target-resource-private-ip-address"]')
        target_port=$(echo "$session_data" | jq -r '.data["target-resource-details"]["target-resource-port"]')

        local_port="${local_port:-$target_port}"

        log_info "Port forwarding session detected"
        echo "SSH Command:"
        echo "ssh -i $ssh_key -N -L ${local_port}:${target_ip}:${target_port} -p 22 ${bastion_user}@host.bastion.<region>.oci.oraclecloud.com"
    else
        log_info "Managed SSH session detected"
        echo "SSH Command from session metadata:"
        echo "$session_data" | jq -r '.data["ssh-metadata"]["command"] // "Command not available"'
    fi
}

# Delete/terminate a session
delete_session() {
    local session_id="$1"

    if [[ -z "$session_id" ]]; then
        log_error "Session OCID required."
        exit 1
    fi

    log_info "Deleting session..."
    oci bastion session delete \
        --session-id "$session_id" \
        --profile "$OCI_PROFILE" \
        --force

    log_success "Session deleted successfully"
}

# Show usage
usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI Bastion Service Operations Wrapper

Commands:
  list-bastions [compartment_id]           List all bastions in compartment
  get-bastion [bastion_id]                 Get bastion details
  list-sessions [bastion_id] [state]       List sessions (state: ACTIVE, DELETED, etc.)

  create-port-forward <bastion_id> <target_host> <target_port> [name] [ttl] [ssh_key]
                                           Create port forwarding session

  create-ssh <bastion_id> <instance_id> [user] [name] [ttl] [ssh_key]
                                           Create managed SSH session

  get-session <session_id>                 Get session details with connection command
  connect <session_id> [local_port] [key]  Show connection command for session
  delete-session <session_id>              Delete/terminate a session

Environment Variables:
  OCI_PROFILE       OCI CLI profile to use (default: DEFAULT)
  BASTION_OCID      Default bastion OCID
  COMPARTMENT_OCID  Default compartment OCID
  DEFAULT_TTL       Default session TTL in seconds (default: 10800)

Examples:
  $(basename "$0") list-bastions ocid1.compartment.oc1..xxx
  $(basename "$0") create-port-forward ocid1.bastion.oc1..xxx 10.0.1.5 22
  $(basename "$0") create-ssh ocid1.bastion.oc1..xxx ocid1.instance.oc1..xxx opc
  $(basename "$0") connect ocid1.bastionsession.oc1..xxx 2222

EOF
}

# Main entry point
main() {
    check_dependencies
    validate_oci_config

    local command="${1:-help}"
    shift || true

    case "$command" in
        list-bastions)
            list_bastions "$@"
            ;;
        get-bastion)
            get_bastion "$@"
            ;;
        list-sessions)
            list_sessions "$@"
            ;;
        create-port-forward)
            create_port_forward_session "$@"
            ;;
        create-ssh)
            create_managed_ssh_session "$@"
            ;;
        get-session)
            get_session "$@"
            ;;
        connect)
            connect_session "$@"
            ;;
        delete-session)
            delete_session "$@"
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
