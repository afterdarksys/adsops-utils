#!/bin/bash
#
# backend-sessions.sh - OCI Backend Service Session Management
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for managing backend service sessions
# including database connections, Redis, and other backend services via OCI Bastion.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"
BASTION_OCID="${BASTION_OCID:-}"

# Jump host configuration
JUMP_HOST="${JUMP_HOST:-}"
JUMP_USER="${JUMP_USER:-opc}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
DEFAULT_TTL="${DEFAULT_TTL:-10800}"

# Default ports
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
REDIS_PORT="${REDIS_PORT:-6379}"
MONGODB_PORT="${MONGODB_PORT:-27017}"

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
# Database Discovery
# ============================================================================

# List Autonomous Databases
list_autonomous_dbs() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing Autonomous Databases..."

    oci db autonomous-database list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."db-workload")\t\(."lifecycle-state")"'
}

# List MySQL Database Systems
list_mysql_dbs() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing MySQL Database Systems..."

    oci mysql db-system list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."mysql-version")\t\(."lifecycle-state")"'
}

# Get MySQL DB System details
get_mysql_db() {
    local db_id="$1"

    if [[ -z "$db_id" ]]; then
        log_error "MySQL DB System OCID required."
        exit 1
    fi

    oci mysql db-system get \
        --db-system-id "$db_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            id: .id,
            displayName: ."display-name",
            mysqlVersion: ."mysql-version",
            ipAddress: .endpoints[0]."ip-address",
            port: .endpoints[0].port,
            state: ."lifecycle-state"
        }'
}

# List PostgreSQL Database Systems
list_postgres_dbs() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing PostgreSQL Database Systems..."

    oci psql db-system list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json 2>/dev/null | jq -r '.data.items[] | "\(.id)\t\(."display-name")\t\(."lifecycle-state")"' || echo "PostgreSQL service not available in this region"
}

# List NoSQL tables
list_nosql_tables() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing NoSQL tables..."

    oci nosql table list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(.name)\t\(."lifecycle-state")"'
}

# ============================================================================
# OCI Bastion Port Forwarding
# ============================================================================

# Create bastion port forward session
bastion_port_forward() {
    local target_ip="$1"
    local target_port="$2"
    local local_port="${3:-$target_port}"
    local bastion_id="${4:-$BASTION_OCID}"

    if [[ -z "$target_ip" || -z "$target_port" || -z "$bastion_id" ]]; then
        log_error "Usage: bastion-forward <target_ip> <target_port> [local_port] [bastion_id]"
        exit 1
    fi

    if [[ ! -f "${SSH_KEY}.pub" ]]; then
        log_error "SSH public key not found: ${SSH_KEY}.pub"
        exit 1
    fi

    log_info "Creating bastion port forward: localhost:$local_port -> $target_ip:$target_port"

    # Create session
    local session_result
    session_result=$(oci bastion session create-port-forwarding \
        --bastion-id "$bastion_id" \
        --display-name "db-$(date +%s)" \
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

    # Get bastion region
    local bastion_info
    bastion_info=$(oci bastion bastion get \
        --bastion-id "$bastion_id" \
        --profile "$OCI_PROFILE" \
        --output json)

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

# Create session in background
bastion_port_forward_bg() {
    local target_ip="$1"
    local target_port="$2"
    local local_port="${3:-$target_port}"
    local bastion_id="${4:-$BASTION_OCID}"
    local pid_file="${5:-/tmp/bastion-tunnel-${local_port}.pid}"

    if [[ -z "$target_ip" || -z "$target_port" || -z "$bastion_id" ]]; then
        log_error "Usage: bastion-forward-bg <target_ip> <target_port> [local_port] [bastion_id]"
        exit 1
    fi

    # Check if already running
    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        log_warn "Tunnel already running on port $local_port (PID: $(cat "$pid_file"))"
        return 0
    fi

    log_info "Creating background port forward: localhost:$local_port -> $target_ip:$target_port"

    # Create session
    local session_result
    session_result=$(oci bastion session create-port-forwarding \
        --bastion-id "$bastion_id" \
        --display-name "db-bg-$(date +%s)" \
        --ssh-public-key-file "${SSH_KEY}.pub" \
        --target-private-ip "$target_ip" \
        --target-port "$target_port" \
        --session-ttl "$DEFAULT_TTL" \
        --profile "$OCI_PROFILE" \
        --wait-for-state ACTIVE \
        --output json)

    local session_id
    session_id=$(echo "$session_result" | jq -r '.data.id')

    # Get bastion region
    local region
    region=$(oci bastion bastion get \
        --bastion-id "$bastion_id" \
        --profile "$OCI_PROFILE" \
        --query 'data."target-vcn-id"' \
        --raw-output | cut -d'.' -f4)

    # Start tunnel in background
    ssh -i "$SSH_KEY" \
        -N -f \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -L "${local_port}:${target_ip}:${target_port}" \
        -p 22 "${session_id}@host.bastion.${region}.oci.oraclecloud.com"

    # Find PID
    local pid
    pid=$(pgrep -f "ssh.*-L ${local_port}:${target_ip}:${target_port}" | head -1)

    if [[ -n "$pid" ]]; then
        echo "$pid" > "$pid_file"
        echo "$session_id" > "${pid_file%.pid}.session"
        log_success "Tunnel created (PID: $pid, Session: $session_id)"
        log_info "Close with: $(basename "$0") close-tunnel $local_port"
    else
        log_error "Failed to create tunnel"
        exit 1
    fi
}

# Close tunnel and delete session
close_tunnel() {
    local local_port="$1"
    local pid_file="/tmp/bastion-tunnel-${local_port}.pid"
    local session_file="/tmp/bastion-tunnel-${local_port}.session"

    if [[ -z "$local_port" ]]; then
        log_error "Local port required."
        exit 1
    fi

    # Kill SSH process
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            log_success "Tunnel process killed (PID: $pid)"
        fi
        rm -f "$pid_file"
    fi

    # Delete bastion session
    if [[ -f "$session_file" ]]; then
        local session_id
        session_id=$(cat "$session_file")
        log_info "Deleting bastion session..."
        oci bastion session delete \
            --session-id "$session_id" \
            --profile "$OCI_PROFILE" \
            --force 2>/dev/null || true
        rm -f "$session_file"
        log_success "Session deleted"
    fi
}

# List active tunnels
list_tunnels() {
    log_info "Active bastion tunnels:"
    echo ""

    for pid_file in /tmp/bastion-tunnel-*.pid; do
        if [[ -f "$pid_file" ]]; then
            local port
            port=$(basename "$pid_file" | sed 's/bastion-tunnel-\(.*\)\.pid/\1/')
            local pid
            pid=$(cat "$pid_file")
            local session=""

            if [[ -f "/tmp/bastion-tunnel-${port}.session" ]]; then
                session=$(cat "/tmp/bastion-tunnel-${port}.session")
            fi

            if kill -0 "$pid" 2>/dev/null; then
                echo "Port $port: PID=$pid (running) Session=$session"
            else
                echo "Port $port: PID=$pid (dead)"
            fi
        fi
    done 2>/dev/null || echo "No active tunnels found"
}

# ============================================================================
# SSH Tunnel Functions
# ============================================================================

# SSH tunnel through jump host
ssh_tunnel() {
    local target_host="$1"
    local target_port="$2"
    local local_port="${3:-$target_port}"
    local jump="${4:-$JUMP_HOST}"
    local user="${5:-$JUMP_USER}"

    if [[ -z "$target_host" || -z "$target_port" || -z "$jump" ]]; then
        log_error "Usage: ssh-tunnel <target_host> <target_port> [local_port] [jump_host] [user]"
        exit 1
    fi

    log_info "Creating SSH tunnel: localhost:$local_port -> $target_host:$target_port (via $jump)"
    ssh -i "$SSH_KEY" -N -L "${local_port}:${target_host}:${target_port}" "${user}@${jump}"
}

# SSH tunnel in background
ssh_tunnel_bg() {
    local target_host="$1"
    local target_port="$2"
    local local_port="${3:-$target_port}"
    local jump="${4:-$JUMP_HOST}"
    local user="${5:-$JUMP_USER}"
    local pid_file="/tmp/ssh-tunnel-${local_port}.pid"

    if [[ -z "$target_host" || -z "$target_port" || -z "$jump" ]]; then
        log_error "Usage: ssh-tunnel-bg <target_host> <target_port> [local_port] [jump_host] [user]"
        exit 1
    fi

    # Check if already running
    if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        log_warn "Tunnel already running on port $local_port"
        return 0
    fi

    log_info "Creating background SSH tunnel: localhost:$local_port -> $target_host:$target_port"

    ssh -i "$SSH_KEY" \
        -N -f \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=60 \
        -L "${local_port}:${target_host}:${target_port}" \
        "${user}@${jump}"

    local pid
    pid=$(pgrep -f "ssh.*-L ${local_port}:${target_host}:${target_port}" | head -1)

    if [[ -n "$pid" ]]; then
        echo "$pid" > "$pid_file"
        log_success "Tunnel created (PID: $pid)"
    fi
}

# ============================================================================
# Database Clients
# ============================================================================

# Connect to PostgreSQL
connect_postgres() {
    local host="${1:-localhost}"
    local database="${2:-postgres}"
    local user="${3:-postgres}"
    local port="${4:-$POSTGRES_PORT}"

    if ! command -v psql &>/dev/null; then
        log_error "psql not found. Install PostgreSQL client."
        exit 1
    fi

    log_info "Connecting to PostgreSQL at $host:$port..."
    psql -h "$host" -p "$port" -U "$user" -d "$database"
}

# Connect to MySQL
connect_mysql() {
    local host="${1:-localhost}"
    local database="${2:-}"
    local user="${3:-root}"
    local port="${4:-$MYSQL_PORT}"

    if ! command -v mysql &>/dev/null; then
        log_error "mysql not found. Install MySQL client."
        exit 1
    fi

    local cmd="mysql -h $host -P $port -u $user"
    if [[ -n "$database" ]]; then
        cmd="$cmd -D $database"
    fi

    log_info "Connecting to MySQL at $host:$port..."
    eval "$cmd -p"
}

# Connect to Redis
connect_redis() {
    local host="${1:-localhost}"
    local port="${2:-$REDIS_PORT}"

    if ! command -v redis-cli &>/dev/null; then
        log_error "redis-cli not found. Install Redis client."
        exit 1
    fi

    log_info "Connecting to Redis at $host:$port..."
    redis-cli -h "$host" -p "$port"
}

# Connect to MongoDB
connect_mongodb() {
    local host="${1:-localhost}"
    local port="${2:-$MONGODB_PORT}"
    local database="${3:-admin}"

    local client=""
    if command -v mongosh &>/dev/null; then
        client="mongosh"
    elif command -v mongo &>/dev/null; then
        client="mongo"
    else
        log_error "mongosh/mongo not found. Install MongoDB client."
        exit 1
    fi

    log_info "Connecting to MongoDB at $host:$port..."
    $client "mongodb://$host:$port/$database"
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI Backend Service Session Management

Database Discovery:
  list-autonomous [compartment]           List Autonomous Databases
  list-mysql [compartment]                List MySQL DB Systems
  get-mysql <db_id>                       Get MySQL DB details
  list-postgres [compartment]             List PostgreSQL DB Systems
  list-nosql [compartment]                List NoSQL tables

OCI Bastion Tunnels:
  bastion-forward <ip> <port> [local] [bastion]
                                          Port forward via bastion (foreground)
  bastion-forward-bg <ip> <port> [local] [bastion]
                                          Port forward via bastion (background)
  close-tunnel <local_port>               Close tunnel and delete session
  list-tunnels                            List active tunnels

SSH Tunnels (via jump host):
  ssh-tunnel <host> <port> [local] [jump] [user]
                                          SSH tunnel (foreground)
  ssh-tunnel-bg <host> <port> [local] [jump] [user]
                                          SSH tunnel (background)

Database Clients:
  postgres [host] [db] [user] [port]      Connect to PostgreSQL
  mysql [host] [db] [user] [port]         Connect to MySQL
  redis [host] [port]                     Connect to Redis
  mongodb [host] [port] [db]              Connect to MongoDB

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
  BASTION_OCID      Default bastion OCID
  JUMP_HOST         Default jump host IP
  JUMP_USER         Default SSH user (default: opc)
  SSH_KEY           SSH private key (default: ~/.ssh/id_rsa)
  DEFAULT_TTL       Session TTL in seconds (default: 10800)

Examples:
  # Create bastion tunnel to MySQL
  $(basename "$0") bastion-forward-bg 10.0.2.100 3306
  $(basename "$0") mysql localhost mydb admin 3306

  # Create SSH tunnel to PostgreSQL
  $(basename "$0") ssh-tunnel-bg 10.0.2.100 5432 5432 10.0.1.5
  $(basename "$0") postgres localhost mydb myuser

  # Close tunnel
  $(basename "$0") close-tunnel 3306

EOF
}

main() {
    check_dependencies

    local command="${1:-help}"
    shift || true

    case "$command" in
        # Discovery
        list-autonomous)
            list_autonomous_dbs "$@"
            ;;
        list-mysql)
            list_mysql_dbs "$@"
            ;;
        get-mysql)
            get_mysql_db "$@"
            ;;
        list-postgres)
            list_postgres_dbs "$@"
            ;;
        list-nosql)
            list_nosql_tables "$@"
            ;;

        # Bastion tunnels
        bastion-forward)
            bastion_port_forward "$@"
            ;;
        bastion-forward-bg)
            bastion_port_forward_bg "$@"
            ;;
        close-tunnel)
            close_tunnel "$@"
            ;;
        list-tunnels)
            list_tunnels "$@"
            ;;

        # SSH tunnels
        ssh-tunnel)
            ssh_tunnel "$@"
            ;;
        ssh-tunnel-bg)
            ssh_tunnel_bg "$@"
            ;;

        # Database clients
        postgres)
            connect_postgres "$@"
            ;;
        mysql)
            connect_mysql "$@"
            ;;
        redis)
            connect_redis "$@"
            ;;
        mongodb)
            connect_mongodb "$@"
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
