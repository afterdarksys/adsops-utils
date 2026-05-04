#!/usr/local/bin/bash
# adsops - Unified AdsOps Toolkit Wrapper
# Context-aware interface to host management, SSH keys, tunnels, and OCI resources
#
# Usage: adsops <command> [options]

set -e

# Script directory
ADSOPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ADSOPS_DIR

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Version
VERSION="1.0.0"

# Auto-load environment on startup
_auto_load_env() {
    local env_file="$ADSOPS_DIR/.env"

    if [ -f "$env_file" ]; then
        while IFS='=' read -r key value; do
            [[ "$key" =~ ^[[:space:]]*# ]] && continue
            [[ -z "$key" ]] && continue
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            [ -z "${!key}" ] && export "$key=$value"
        done < "$env_file"
    fi
}

# Source helper modules
_load_modules() {
    [ -f "$ADSOPS_DIR/adsops-context" ] && source "$ADSOPS_DIR/adsops-context"
    [ -f "$ADSOPS_DIR/adsops-discover" ] && source "$ADSOPS_DIR/adsops-discover"
}

# Initialize
_auto_load_env
_load_modules

# Smart SSH - checks resource type before connecting
smart_ssh() {
    local target="$1"
    shift
    local ssh_args="$@"

    # Extract host from target (user@host or just host)
    local host="${target##*@}"
    local user="${target%@*}"
    [ "$user" = "$target" ] && user=""

    echo -e "${CYAN}Analyzing target: $host${NC}"

    # Check if this is a load balancer
    local resource_info
    resource_info=$(identify_resource "$host" 2>/dev/null || echo "unknown::")
    local resource_type="${resource_info%%:*}"

    case "$resource_type" in
        load-balancer|network-load-balancer)
            echo ""
            echo -e "${RED}ERROR: Cannot SSH to a load balancer!${NC}"
            echo -e "${YELLOW}$host is a $resource_type${NC}"
            echo ""
            echo "Getting backend instances..."

            local resource_id="${resource_info##*:}"
            if [ -n "$resource_id" ]; then
                local backends=$(get_lb_backends "$resource_id" 2>/dev/null)
                if [ -n "$backends" ]; then
                    echo ""
                    echo -e "${GREEN}Available backend instances:${NC}"
                    echo "$backends" | jq -r '.[] | .backends[]? | "  \(.["ip-address"])"' | sort -u
                    echo ""
                    echo "Connect to a backend instance instead:"
                    local first_backend=$(echo "$backends" | jq -r '.[0].backends[0]."ip-address" // empty')
                    if [ -n "$first_backend" ]; then
                        echo -e "  ${CYAN}adsops ssh ${user:+$user@}$first_backend${NC}"
                    fi
                fi
            fi
            return 1
            ;;
        instance)
            echo -e "${GREEN}Target is a compute instance - proceeding with SSH${NC}"
            ;;
        db-system)
            echo ""
            echo -e "${YELLOW}WARNING: $host is a database system${NC}"
            echo "For database access, use a database client instead of SSH."
            echo "For OS-level access, consider using OCI Bastion service."
            echo ""
            read -p "Continue with SSH anyway? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                return 1
            fi
            ;;
        *)
            # Unknown resource - check connectivity
            echo -e "${YELLOW}Resource not found in OCI, checking connectivity...${NC}"
            ;;
    esac

    # Detect context and determine if tunnel is needed
    adsops_detect_context

    # Check direct connectivity
    if _can_reach_direct "$host" "22"; then
        echo -e "${GREEN}Direct SSH connection available${NC}"

        # Try to find SSH key
        local key_file
        key_file=$("$ADSOPS_DIR/ssh-key-tracker" get "$host" ${user:+$user} 2>/dev/null || echo "")

        if [ -n "$key_file" ] && [ -f "$key_file" ]; then
            echo -e "Using key: ${CYAN}$key_file${NC}"
            exec ssh -i "$key_file" ${user:+$user@}$host $ssh_args
        else
            exec ssh ${user:+$user@}$host $ssh_args
        fi
    else
        echo -e "${YELLOW}Direct connection not available${NC}"

        # Check if we have a tunnel endpoint for this
        local endpoint_key=$(echo "$host" | tr '.' '_')
        local tunnel_host="${ADSOPS_TUNNEL_HOSTS[$endpoint_key]}"

        # Also check by known endpoints
        for ep in "${!ADSOPS_ENDPOINTS[@]}"; do
            local ep_addr="${ADSOPS_ENDPOINTS[$ep]}"
            if [[ "$ep_addr" == "$host:"* ]] || [[ "$ep_addr" == *":$host" ]]; then
                tunnel_host="${ADSOPS_TUNNEL_HOSTS[$ep]}"
                break
            fi
        done

        if [ -n "$tunnel_host" ]; then
            echo -e "${GREEN}Cloudflare tunnel available: $tunnel_host${NC}"
            echo ""
            echo "Connecting via tunnel..."
            exec cloudflared access ssh --hostname "$tunnel_host"
        else
            echo -e "${RED}No tunnel configured for this host${NC}"
            echo ""
            echo "Options:"
            echo "  1. Use OCI Bastion service"
            echo "  2. Configure a Cloudflare tunnel"
            echo "  3. Connect via VPN"
            return 1
        fi
    fi
}

# Smart connect - determines best way to connect to any resource
smart_connect() {
    local target="$1"

    if [ -z "$target" ]; then
        echo "Usage: adsops connect <hostname-or-ip>"
        return 1
    fi

    get_access_recommendation "$target"
}

# Wrapper for hostctl with auto-env
run_hostctl() {
    # Ensure env vars are set
    if [ -z "$INVENTORY_DB_USER" ]; then
        echo -e "${RED}INVENTORY_DB_USER not set${NC}"
        echo "Set it in $ADSOPS_DIR/.env or export it"
        return 1
    fi

    "$ADSOPS_DIR/hostctl" "$@"
}

# Wrapper for infractl
_run_infractl() {
    local bin="$ADSOPS_DIR/infractl"
    if ! command -v "$bin" &>/dev/null && ! [ -f "$bin" ]; then
        # Fall back to PATH
        bin="infractl"
    fi
    if ! command -v "$bin" &>/dev/null; then
        echo -e "${RED}infractl not found. Build it:${NC}"
        echo "  cd $ADSOPS_DIR/../infractl && make build && cp infractl $ADSOPS_DIR/"
        return 1
    fi
    "$bin" "$@"
}

# Fetch statsagent JSON from a remote host via SSH
_stats_from_host() {
    local host="$1"
    local port="${STATSAGENT_PORT:-9100}"
    # Try direct HTTP first (if statsagent port is reachable), otherwise via SSH
    if curl -sf --connect-timeout 3 "http://$host:$port/stats" 2>/dev/null; then
        return 0
    fi
    # Fall back to fetching via SSH
    ssh "$host" "curl -sf http://localhost:$port/stats 2>/dev/null || echo '{\"error\":\"statsagent not running\"}'"
}

# Wrapper for blackout with auto-env
run_blackout() {
    # Ensure env vars are set
    if [ -z "$DB_USER" ]; then
        # Try to use INVENTORY_DB_USER as fallback
        export DB_USER="${INVENTORY_DB_USER:-apiproxy}"
        export DB_PASSWORD="${INVENTORY_DB_PASSWORD:-apiproxy_secure_2026}"
        export DB_NAME="${DB_NAME:-apiproxy}"
    fi

    "$ADSOPS_DIR/blackout" "$@"
}

# Show status overview
show_status() {
    echo -e "${BOLD}${BLUE}=== AdsOps Toolkit Status ===${NC}"
    echo ""

    # Context
    adsops_detect_context
    echo -e "${CYAN}Execution Context:${NC} $ADSOPS_CONTEXT ($ADSOPS_NETWORK_CONTEXT)"
    echo ""

    # Environment
    echo -e "${CYAN}Environment:${NC}"
    [ -n "$INVENTORY_DB_USER" ] && echo "  Inventory DB: configured" || echo -e "  Inventory DB: ${RED}not configured${NC}"
    [ -n "$CLOUDFLARE_TUNNEL_ID" ] && echo "  CF Tunnel: configured" || echo "  CF Tunnel: not configured"
    echo ""

    # Tools
    echo -e "${CYAN}Available Tools:${NC}"
    [ -x "$ADSOPS_DIR/hostctl" ] && echo -e "  ${GREEN}hostctl${NC} - Host inventory management" || echo -e "  ${RED}hostctl${NC} - not found"
    [ -x "$ADSOPS_DIR/blackout" ] && echo -e "  ${GREEN}blackout${NC} - Maintenance window management" || echo -e "  ${RED}blackout${NC} - not found"
    [ -x "$ADSOPS_DIR/ssh-key-tracker" ] && echo -e "  ${GREEN}ssh-key-tracker${NC} - SSH key management" || echo -e "  ${RED}ssh-key-tracker${NC} - not found"
    [ -x "$ADSOPS_DIR/adsops-context" ] && echo -e "  ${GREEN}adsops-context${NC} - Context detection" || echo -e "  ${RED}adsops-context${NC} - not found"
    [ -x "$ADSOPS_DIR/adsops-discover" ] && echo -e "  ${GREEN}adsops-discover${NC} - OCI discovery" || echo -e "  ${RED}adsops-discover${NC} - not found"
    command -v cloudflared &>/dev/null && echo -e "  ${GREEN}cloudflared${NC} - Cloudflare tunnel client" || echo -e "  ${YELLOW}cloudflared${NC} - not installed"
    command -v oci &>/dev/null && echo -e "  ${GREEN}oci${NC} - OCI CLI" || echo -e "  ${YELLOW}oci${NC} - not installed"
    echo ""
}

# Show help
show_help() {
    cat <<EOF
${BOLD}adsops${NC} - Unified AdsOps Toolkit (v$VERSION)

${BOLD}USAGE:${NC}
    adsops <command> [options]

${BOLD}SMART COMMANDS:${NC}
    ssh <target>           Smart SSH with LB detection and tunnel fallback
    connect <target>       Get access recommendation for any resource

${BOLD}CONTEXT COMMANDS:${NC}
    context                Show execution context (host/docker/k8s)
    status                 Show toolkit status overview

${BOLD}DISCOVERY COMMANDS:${NC}
    discover [type]        Discover OCI resources
    identify <target>      Identify resource type from IP/hostname
    access <target>        Alias for 'connect'

${BOLD}HOST MANAGEMENT:${NC}
    host list [filters]    List hosts from inventory
    host add <name> ...    Add host to inventory
    host show <name>       Show host details
    host search <query>    Search hosts
    import                 Import hosts from ~/.ssh/config into inventory

${BOLD}INFRA MANAGEMENT (Docker + k3s):${NC}
    scan [host|--all]      Probe hosts: OS, Docker, k3s, statsagent
    infra status [host]    Docker + k3s overview for a host
    docker <cmd> <host>    Manage Docker containers (ls/start/stop/rm/logs/exec/pull/stats)
    k3s <cmd> <host>       Manage k3s clusters (nodes/pods/svc/logs/apply/kubeconfig)
    stats [host]           Fetch statsagent JSON from a host

${BOLD}MAINTENANCE:${NC}
    blackout <args>        Manage maintenance windows

${BOLD}BASTION & ACCESS:${NC}
    bastion <cmd>          OCI Bastion session management
    jump <cmd>             Jump host access
    backend <cmd>          Backend service connections

${BOLD}OS MANAGEMENT:${NC}
    osm <cmd>              OS Management session & agent operations
    os-mgmt <cmd>          OS Management service operations
    patch <cmd>            Patch management operations

${BOLD}SECRETS & STATE:${NC}
    secrets <cmd>          OCI Vault secrets management (also: param, params)
    state <cmd>            Terraform state management

${BOLD}SSH KEYS:${NC}
    keys list              List SSH key mappings
    keys add <args>        Add SSH key mapping
    keys test <host>       Test SSH key for host
    keys scan <host>       Scan for working keys

${BOLD}TUNNEL:${NC}
    tunnel <endpoint>      Start tunnel for endpoint
    need-tunnel <ep>       Check if tunnel needed

${BOLD}CONFIGURATION:${NC}
    env                    Show environment variables
    config                 Edit configuration

${BOLD}EXAMPLES:${NC}
    adsops ssh 132.145.179.230           # Smart SSH to IP
    adsops connect keycloak-db           # Get access recommendation
    adsops discover                      # List all OCI resources
    adsops host list --status active     # List active hosts
    adsops import                        # Import ~/.ssh/config hosts into inventory
    adsops scan --all                    # Probe all hosts for Docker/k3s
    adsops infra status web-01           # Docker + k3s overview for web-01
    adsops docker ls web-01              # List containers on web-01
    adsops docker logs web-01 myapp -f   # Follow container logs
    adsops k3s pods web-01               # List all pods
    adsops k3s apply web-01 -f app.yaml  # Apply a manifest
    adsops stats web-01                  # Show statsagent JSON from web-01
    adsops keys list                     # Show SSH key mappings
    adsops tunnel keycloak_db            # Start DB tunnel
    adsops bastion list-sessions         # List OCI bastion sessions
    adsops jump connect 10.0.1.5         # Connect via jump host
    adsops osm list-agents               # List OSM managed instances
    adsops patch status                  # Show patch compliance status
    adsops secrets get my-secret         # Get a secret from OCI Vault
    adsops state list                    # List Terraform state resources
    adsops backend connect-postgres 10.0.1.5 5432 mydb admin

${BOLD}ENVIRONMENT:${NC}
    ADSOPS_DIR             Toolkit directory (default: /usr/local/sshkeys)
    OPSCTL_ENV             Environment for opsctl modules (dev/staging/prod)
    INVENTORY_DB_USER      Database username for inventory
    INVENTORY_DB_PASSWORD  Database password for inventory

EOF
}

# Main dispatcher
main() {
    local command="${1:-help}"
    shift || true

    case "$command" in
        # Smart commands
        ssh)
            smart_ssh "$@"
            ;;
        connect|access)
            smart_connect "$@"
            ;;

        # Context
        context)
            "$ADSOPS_DIR/adsops-context" context "$@"
            ;;
        status)
            show_status
            ;;

        # Discovery
        discover|disc)
            "$ADSOPS_DIR/adsops-discover" list "$@"
            ;;
        identify|id)
            "$ADSOPS_DIR/adsops-discover" identify "$@"
            ;;

        # Host management
        host|hosts)
            local subcmd="${1:-list}"
            shift || true
            run_hostctl "$subcmd" "$@"
            ;;

        # Blackout
        blackout|maint|maintenance)
            run_blackout "$@"
            ;;

        # SSH Keys
        keys|key|ssh-keys)
            local subcmd="${1:-list}"
            shift || true
            "$ADSOPS_DIR/ssh-key-tracker" "$subcmd" "$@"
            ;;

        # Tunnel
        tunnel)
            "$ADSOPS_DIR/adsops-context" tunnel "$@"
            ;;
        need-tunnel)
            "$ADSOPS_DIR/adsops-context" need-tunnel "$@"
            ;;

        # Environment
        env)
            "$ADSOPS_DIR/adsops-context" env
            ;;
        config)
            ${EDITOR:-vim} "$ADSOPS_DIR/.env"
            ;;

        # opsctl modules
        bastion)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} bastion "$@"
            ;;
        osm|osm-session)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} osm "$@"
            ;;
        patch|patch-mgmt)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} patch "$@"
            ;;
        secrets|secret|param|params)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} secrets "$@"
            ;;
        state|tf-state)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} state "$@"
            ;;
        os-mgmt|osmgmt)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} os-mgmt "$@"
            ;;
        jump|jump-host)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} jump "$@"
            ;;
        backend)
            python3 "$ADSOPS_DIR/../opsctl.py" ${OPSCTL_ENV:+--env $OPSCTL_ENV} backend "$@"
            ;;

        # SSH config import → hostctl
        import|import-hosts)
            run_hostctl import ssh-config "$@"
            ;;

        # infractl: scan all hosts
        scan)
            _run_infractl scan "$@"
            ;;

        # infractl: status overview
        infra|infra-status)
            local subcmd="${1:-status}"
            shift || true
            _run_infractl "$subcmd" "$@"
            ;;

        # Docker management
        docker|container|containers)
            local subcmd="${1:-ls}"
            shift || true
            _run_infractl docker "$subcmd" "$@"
            ;;

        # k3s management
        k3s|k8s|kube|kubectl)
            local subcmd="${1:-pods}"
            shift || true
            _run_infractl k3s "$subcmd" "$@"
            ;;

        # statsagent: fetch JSON from a host
        stats|statsagent)
            local target="${1:-}"
            if [ -z "$target" ]; then
                echo -e "${RED}Usage: adsops stats <host>${NC}"
                exit 1
            fi
            echo -e "${CYAN}Fetching stats from $target...${NC}"
            _stats_from_host "$target"
            ;;

        # Direct tool access
        hostctl)
            run_hostctl "$@"
            ;;

        infractl)
            _run_infractl "$@"
            ;;

        # Help
        help|--help|-h)
            show_help
            ;;

        version|--version|-v)
            echo "adsops version $VERSION"
            ;;

        # Unknown - check if it's an IP/hostname for smart connect
        *)
            if [[ "$command" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [[ "$command" =~ \. ]]; then
                smart_connect "$command" "$@"
            else
                echo -e "${RED}Unknown command: $command${NC}"
                echo "Run 'adsops help' for usage"
                exit 1
            fi
            ;;
    esac
}

main "$@"
