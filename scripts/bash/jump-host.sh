#!/bin/bash
#
# jump-host.sh - OCI Bastion & Jump Host Access
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for accessing managed jump hosts
# via OCI Bastion service with SSH key management.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"
BASTION_OCID="${BASTION_OCID:-}"
JUMP_HOST_OCID="${JUMP_HOST_OCID:-}"
JUMP_HOST_IP="${JUMP_HOST_IP:-}"
JUMP_HOST_USER="${JUMP_HOST_USER:-opc}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
DEFAULT_TTL="${DEFAULT_TTL:-10800}"  # 3 hours

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
    for cmd in oci jq ssh; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Missing required dependency: $cmd"
            exit 1
        fi
    done
}

# ============================================================================
# Jump Host Discovery
# ============================================================================

# List available jump hosts (tagged instances)
list_jump_hosts() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing jump hosts..."

    oci compute instance list \
        --compartment-id "$compartment" \
        --lifecycle-state RUNNING \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | select(."freeform-tags".role == "jumphost" or ."freeform-tags".role == "bastion" or (."display-name" | test("jump|bastion"; "i"))) | "\(.id)\t\(."display-name")\t\(."lifecycle-state")"'
}

# Get jump host details
get_jump_host() {
    local instance_id="${1:-$JUMP_HOST_OCID}"

    if [[ -z "$instance_id" ]]; then
        log_error "Instance OCID required."
        exit 1
    fi

    oci compute instance get \
        --instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            id: .id,
            name: ."display-name",
            state: ."lifecycle-state",
            shape: .shape,
            availabilityDomain: ."availability-domain",
            timeCreated: ."time-created"
        }'
}

# Get instance VNIC and IP
get_instance_ip() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Instance OCID required."
        exit 1
    fi

    # Get compartment
    local compartment
    compartment=$(oci compute instance get \
        --instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --query 'data."compartment-id"' \
        --raw-output)

    # Get VNIC attachments
    local vnic_id
    vnic_id=$(oci compute vnic-attachment list \
        --compartment-id "$compartment" \
        --instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --query 'data[0]."vnic-id"' \
        --raw-output)

    # Get VNIC details
    oci network vnic get \
        --vnic-id "$vnic_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '{privateIp: .data."private-ip", publicIp: .data."public-ip", hostname: .data."hostname-label"}'
}

# ============================================================================
# OCI Bastion Functions
# ============================================================================

# List bastions
list_bastions() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing bastions..."

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
        log_error "Bastion OCID required."
        exit 1
    fi

    oci bastion bastion get \
        --bastion-id "$bastion_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# List active sessions
list_sessions() {
    local bastion_id="${1:-$BASTION_OCID}"

    if [[ -z "$bastion_id" ]]; then
        log_error "Bastion OCID required."
        exit 1
    fi

    log_info "Listing active sessions..."

    oci bastion session list \
        --bastion-id "$bastion_id" \
        --session-lifecycle-state ACTIVE \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."session-type")\t\(."time-created")"'
}

# ============================================================================
# Connect Functions
# ============================================================================

# Connect via managed SSH session
connect() {
    local instance_id="${1:-$JUMP_HOST_OCID}"
    local bastion_id="${2:-$BASTION_OCID}"
    local user="${3:-$JUMP_HOST_USER}"

    if [[ -z "$instance_id" || -z "$bastion_id" ]]; then
        log_error "Usage: connect <instance_id> <bastion_id> [user]"
        exit 1
    fi

    if [[ ! -f "${SSH_KEY}.pub" ]]; then
        log_error "SSH public key not found: ${SSH_KEY}.pub"
        exit 1
    fi

    log_info "Creating managed SSH session..."

    local session_result
    session_result=$(oci bastion session create-managed-ssh \
        --bastion-id "$bastion_id" \
        --display-name "jump-$(date +%s)" \
        --ssh-public-key-file "${SSH_KEY}.pub" \
        --target-resource-id "$instance_id" \
        --target-os-username "$user" \
        --session-ttl "$DEFAULT_TTL" \
        --profile "$OCI_PROFILE" \
        --wait-for-state ACTIVE \
        --output json)

    local session_id
    session_id=$(echo "$session_result" | jq -r '.data.id')

    log_success "Session created: $session_id"

    # Get connection command
    local ssh_cmd
    ssh_cmd=$(oci bastion session get \
        --session-id "$session_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq -r '.data["ssh-metadata"].command')

    # Replace placeholder with actual key
    ssh_cmd=$(echo "$ssh_cmd" | sed "s|<privateKey>|$SSH_KEY|g")

    log_info "Connecting..."
    eval "$ssh_cmd"
}

# Port forward through bastion
port_forward() {
    local target_ip="${1:-$JUMP_HOST_IP}"
    local target_port="$2"
    local local_port="${3:-$target_port}"
    local bastion_id="${4:-$BASTION_OCID}"

    if [[ -z "$target_ip" || -z "$target_port" || -z "$bastion_id" ]]; then
        log_error "Usage: port-forward <target_ip> <target_port> [local_port] [bastion_id]"
        exit 1
    fi

    if [[ ! -f "${SSH_KEY}.pub" ]]; then
        log_error "SSH public key not found: ${SSH_KEY}.pub"
        exit 1
    fi

    log_info "Creating port forwarding session: localhost:$local_port -> $target_ip:$target_port"

    local session_result
    session_result=$(oci bastion session create-port-forwarding \
        --bastion-id "$bastion_id" \
        --display-name "pf-$(date +%s)" \
        --ssh-public-key-file "${SSH_KEY}.pub" \
        --target-private-ip "$target_ip" \
        --target-port "$target_port" \
        --session-ttl "$DEFAULT_TTL" \
        --profile "$OCI_PROFILE" \
        --wait-for-state ACTIVE \
        --output json)

    local session_id
    session_id=$(echo "$session_result" | jq -r '.data.id')

    log_success "Session created: $session_id"

    # Get bastion endpoint info
    local bastion_info
    bastion_info=$(oci bastion bastion get \
        --bastion-id "$bastion_id" \
        --profile "$OCI_PROFILE" \
        --output json)

    # Extract region from VCN OCID
    local region
    region=$(echo "$bastion_info" | jq -r '.data."target-vcn-id"' | cut -d'.' -f4)

    local ssh_cmd="ssh -i $SSH_KEY -N -L ${local_port}:${target_ip}:${target_port} -p 22 $session_id@host.bastion.${region}.oci.oraclecloud.com"

    echo ""
    log_info "Port forwarding command:"
    echo "$ssh_cmd"
    echo ""
    log_info "Starting tunnel (Ctrl+C to stop)..."

    eval "$ssh_cmd"
}

# Create session and return connection info (non-interactive)
create_session() {
    local session_type="$1"  # ssh or port-forward
    local bastion_id="${2:-$BASTION_OCID}"

    shift 2

    if [[ "$session_type" == "ssh" ]]; then
        local instance_id="$1"
        local user="${2:-$JUMP_HOST_USER}"

        if [[ -z "$instance_id" || -z "$bastion_id" ]]; then
            log_error "Usage: create-session ssh <bastion_id> <instance_id> [user]"
            exit 1
        fi

        log_info "Creating managed SSH session..."

        oci bastion session create-managed-ssh \
            --bastion-id "$bastion_id" \
            --display-name "ssh-$(date +%s)" \
            --ssh-public-key-file "${SSH_KEY}.pub" \
            --target-resource-id "$instance_id" \
            --target-os-username "$user" \
            --session-ttl "$DEFAULT_TTL" \
            --profile "$OCI_PROFILE" \
            --wait-for-state ACTIVE \
            --output json | jq '.data | {id: .id, type: ."session-type", command: ."ssh-metadata".command}'

    elif [[ "$session_type" == "port-forward" ]]; then
        local target_ip="$1"
        local target_port="$2"

        if [[ -z "$target_ip" || -z "$target_port" || -z "$bastion_id" ]]; then
            log_error "Usage: create-session port-forward <bastion_id> <target_ip> <target_port>"
            exit 1
        fi

        log_info "Creating port forwarding session..."

        oci bastion session create-port-forwarding \
            --bastion-id "$bastion_id" \
            --display-name "pf-$(date +%s)" \
            --ssh-public-key-file "${SSH_KEY}.pub" \
            --target-private-ip "$target_ip" \
            --target-port "$target_port" \
            --session-ttl "$DEFAULT_TTL" \
            --profile "$OCI_PROFILE" \
            --wait-for-state ACTIVE \
            --output json | jq '.data | {id: .id, type: ."session-type"}'
    else
        log_error "Unknown session type: $session_type (use 'ssh' or 'port-forward')"
        exit 1
    fi
}

# Get session details
get_session() {
    local session_id="$1"

    if [[ -z "$session_id" ]]; then
        log_error "Session OCID required."
        exit 1
    fi

    oci bastion session get \
        --session-id "$session_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# Delete session
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

    log_success "Session deleted"
}

# ============================================================================
# Direct SSH Functions (for public jump hosts)
# ============================================================================

# Direct SSH connect
direct_connect() {
    local host="${1:-$JUMP_HOST_IP}"
    local user="${2:-$JUMP_HOST_USER}"

    if [[ -z "$host" ]]; then
        log_error "Host IP required."
        exit 1
    fi

    log_info "Connecting to $user@$host..."
    ssh -i "$SSH_KEY" "$user@$host"
}

# SSH tunnel through public jump host
tunnel() {
    local jump_host="${1:-$JUMP_HOST_IP}"
    local target_host="$2"
    local target_port="$3"
    local local_port="${4:-$target_port}"
    local user="${5:-$JUMP_HOST_USER}"

    if [[ -z "$jump_host" || -z "$target_host" || -z "$target_port" ]]; then
        log_error "Usage: tunnel <jump_host> <target_host> <target_port> [local_port] [user]"
        exit 1
    fi

    log_info "Creating tunnel: localhost:$local_port -> $target_host:$target_port (via $jump_host)"
    ssh -i "$SSH_KEY" -N -L "${local_port}:${target_host}:${target_port}" "${user}@${jump_host}"
}

# ProxyJump connect
proxy() {
    local jump_host="${1:-$JUMP_HOST_IP}"
    local target_host="$2"
    local target_user="${3:-$JUMP_HOST_USER}"
    local jump_user="${4:-$JUMP_HOST_USER}"

    if [[ -z "$jump_host" || -z "$target_host" ]]; then
        log_error "Usage: proxy <jump_host> <target_host> [target_user] [jump_user]"
        exit 1
    fi

    log_info "Connecting to $target_host via $jump_host..."
    ssh -i "$SSH_KEY" -J "${jump_user}@${jump_host}" "${target_user}@${target_host}"
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI Bastion & Jump Host Access

Discovery:
  list [compartment]                      List available jump hosts
  get [instance_id]                       Get jump host details
  get-ip <instance_id>                    Get instance IP addresses

Bastions:
  list-bastions [compartment]             List bastions
  get-bastion [bastion_id]                Get bastion details
  list-sessions [bastion_id]              List active sessions

Connect via Bastion:
  connect <instance_id> <bastion_id> [user]
                                          Create session and connect
  port-forward <target_ip> <port> [local] [bastion_id]
                                          Create port forwarding session

Session Management:
  create-session ssh <bastion_id> <instance_id> [user]
                                          Create SSH session (non-interactive)
  create-session port-forward <bastion_id> <target_ip> <port>
                                          Create port forward session
  get-session <session_id>                Get session details
  delete-session <session_id>             Delete session

Direct SSH (public jump hosts):
  direct [host] [user]                    Direct SSH connection
  tunnel <jump> <target> <port> [local] [user]
                                          SSH tunnel through jump host
  proxy <jump> <target> [target_user] [jump_user]
                                          ProxyJump connection

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
  BASTION_OCID      Default bastion OCID
  JUMP_HOST_OCID    Default jump host instance OCID
  JUMP_HOST_IP      Default jump host IP
  JUMP_HOST_USER    Default SSH user (default: opc)
  SSH_KEY           SSH private key path (default: ~/.ssh/id_rsa)
  DEFAULT_TTL       Session TTL in seconds (default: 10800)

Examples:
  $(basename "$0") list
  $(basename "$0") connect ocid1.instance.oc1..xxx ocid1.bastion.oc1..xxx
  $(basename "$0") port-forward 10.0.2.100 5432 5432
  $(basename "$0") tunnel 10.0.1.5 10.0.2.100 5432

EOF
}

main() {
    check_dependencies

    local command="${1:-help}"
    shift || true

    case "$command" in
        # Discovery
        list)
            list_jump_hosts "$@"
            ;;
        get)
            get_jump_host "$@"
            ;;
        get-ip)
            get_instance_ip "$@"
            ;;

        # Bastions
        list-bastions)
            list_bastions "$@"
            ;;
        get-bastion)
            get_bastion "$@"
            ;;
        list-sessions)
            list_sessions "$@"
            ;;

        # Connect
        connect)
            connect "$@"
            ;;
        port-forward)
            port_forward "$@"
            ;;

        # Session management
        create-session)
            create_session "$@"
            ;;
        get-session)
            get_session "$@"
            ;;
        delete-session)
            delete_session "$@"
            ;;

        # Direct SSH
        direct)
            direct_connect "$@"
            ;;
        tunnel)
            tunnel "$@"
            ;;
        proxy)
            proxy "$@"
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

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
