#!/bin/bash
#
# patch-management.sh - OCI OS Management Patch Operations
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for OCI OS Management patching,
# including update management, errata, and security patches.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"

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
    for cmd in oci jq; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Missing required dependency: $cmd"
            exit 1
        fi
    done
}

# ============================================================================
# Managed Instance Functions
# ============================================================================

# List managed instances with their patch status
list_instances() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing managed instances..."

    oci os-management managed-instance list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(.status)\t\(."updates-available" // 0) updates"'
}

# Get detailed instance info
get_instance() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    oci os-management managed-instance get \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            id: .id,
            displayName: ."display-name",
            osFamily: ."os-family",
            osName: ."os-name",
            osVersion: ."os-version",
            status: .status,
            updatesAvailable: ."updates-available",
            securityUpdatesAvailable: ."security-updates-available",
            bugUpdatesAvailable: ."bug-updates-available",
            enhancementUpdatesAvailable: ."enhancement-updates-available"
        }'
}

# ============================================================================
# Available Updates Functions
# ============================================================================

# List available updates for an instance
list_available_updates() {
    local instance_id="$1"
    local update_type="${2:-ALL}"  # SECURITY, BUGFIX, ENHANCEMENT, ALL

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_info "Listing available $update_type updates..."

    if [[ "$update_type" == "ALL" ]]; then
        oci os-management managed-instance list-available-updates \
            --managed-instance-id "$instance_id" \
            --profile "$OCI_PROFILE" \
            --all \
            --output json | jq -r '.data[] | "\(."display-name")\t\(.version)\t\(."update-type")"'
    else
        oci os-management managed-instance list-available-updates \
            --managed-instance-id "$instance_id" \
            --update-type "$update_type" \
            --profile "$OCI_PROFILE" \
            --all \
            --output json | jq -r '.data[] | "\(."display-name")\t\(.version)\t\(."update-type")"'
    fi
}

# List security updates only
list_security_updates() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_info "Listing security updates..."

    oci os-management managed-instance list-available-updates \
        --managed-instance-id "$instance_id" \
        --update-type SECURITY \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(."display-name")\t\(.version)"'
}

# Count available updates by type
count_updates() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_info "Counting updates by type..."

    local instance_data
    instance_data=$(oci os-management managed-instance get \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --output json)

    echo "$instance_data" | jq '.data | {
        total: ."updates-available",
        security: ."security-updates-available",
        bug: ."bug-updates-available",
        enhancement: ."enhancement-updates-available"
    }'
}

# ============================================================================
# Install Updates Functions
# ============================================================================

# Install all updates on instance
install_all_updates() {
    local instance_id="$1"
    local update_type="${2:-ALL}"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_warn "Installing $update_type updates on instance: $instance_id"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    log_info "Installing updates..."

    oci os-management managed-instance install-all-updates \
        --managed-instance-id "$instance_id" \
        --update-type "$update_type" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'

    log_success "Update installation initiated"
}

# Install specific package update
install_package_update() {
    local instance_id="$1"
    local package_name="$2"

    if [[ -z "$instance_id" || -z "$package_name" ]]; then
        log_error "Usage: install-package <instance_id> <package_name>"
        exit 1
    fi

    log_info "Installing package update: $package_name"

    oci os-management managed-instance install-package-update \
        --managed-instance-id "$instance_id" \
        --software-package-name "$package_name" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'

    log_success "Package update installation initiated"
}

# Install security updates only
install_security_updates() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_warn "Installing SECURITY updates on instance: $instance_id"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci os-management managed-instance install-all-updates \
        --managed-instance-id "$instance_id" \
        --update-type SECURITY \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'

    log_success "Security update installation initiated"
}

# ============================================================================
# Errata Functions
# ============================================================================

# List erratas (security advisories)
list_erratas() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing erratas..."

    oci os-management errata list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.name)\t\(."advisory-type")\t\(.synopsis)"'
}

# Get errata details
get_errata() {
    local errata_name="$1"
    local compartment="${2:-$COMPARTMENT_OCID}"

    if [[ -z "$errata_name" || -z "$compartment" ]]; then
        log_error "Usage: get-errata <errata_name> [compartment]"
        exit 1
    fi

    oci os-management errata get \
        --errata-name "$errata_name" \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# List erratas affecting instance
list_instance_erratas() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_info "Listing erratas affecting instance..."

    oci os-management managed-instance list-errata \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.name)\t\(."advisory-type")\t\(.synopsis)"'
}

# ============================================================================
# Installed Packages Functions
# ============================================================================

# List installed packages
list_installed_packages() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    log_info "Listing installed packages..."

    oci os-management managed-instance list-installed-packages \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(."display-name")\t\(.version)\t\(.architecture)"'
}

# Search installed packages
search_packages() {
    local instance_id="$1"
    local search_term="$2"

    if [[ -z "$instance_id" || -z "$search_term" ]]; then
        log_error "Usage: search-packages <instance_id> <search_term>"
        exit 1
    fi

    log_info "Searching packages matching: $search_term"

    oci os-management managed-instance list-installed-packages \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r ".data[] | select(.\"display-name\" | test(\"$search_term\"; \"i\")) | \"\(.\"display-name\")\t\(.version)\""
}

# ============================================================================
# Scheduled Jobs Functions
# ============================================================================

# List patch-related scheduled jobs
list_patch_jobs() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing patch scheduled jobs..."

    oci os-management scheduled-job list \
        --compartment-id "$compartment" \
        --operation-type UPDATEALL \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."schedule-type")\t\(."lifecycle-state")"'
}

# ============================================================================
# Work Request Functions
# ============================================================================

# Get patch work request status
get_work_request() {
    local work_request_id="$1"

    if [[ -z "$work_request_id" ]]; then
        log_error "Work request OCID required."
        exit 1
    fi

    oci os-management work-request get \
        --work-request-id "$work_request_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            id: .id,
            operationType: ."operation-type",
            status: .status,
            percentComplete: ."percent-complete",
            timeStarted: ."time-started",
            timeFinished: ."time-finished"
        }'
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI OS Management Patch Operations

Instance Info:
  list [compartment]                      List managed instances with patch status
  get <instance_id>                       Get detailed instance info

Available Updates:
  list-updates <instance_id> [type]       List available updates (SECURITY/BUGFIX/ENHANCEMENT/ALL)
  list-security <instance_id>             List security updates only
  count <instance_id>                     Count updates by type

Install Updates:
  install-all <instance_id> [type]        Install all updates
  install-security <instance_id>          Install security updates only
  install-package <instance_id> <pkg>     Install specific package update

Erratas:
  list-erratas [compartment]              List erratas (security advisories)
  get-errata <name> [compartment]         Get errata details
  instance-erratas <instance_id>          List erratas affecting instance

Packages:
  list-packages <instance_id>             List installed packages
  search-packages <instance_id> <term>    Search installed packages

Jobs:
  list-jobs [compartment]                 List patch scheduled jobs
  get-request <work_request_id>           Get work request status

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID

Examples:
  $(basename "$0") list
  $(basename "$0") list-updates ocid1.managedinstance.oc1..xxx SECURITY
  $(basename "$0") install-security ocid1.managedinstance.oc1..xxx
  $(basename "$0") list-erratas

EOF
}

main() {
    check_dependencies

    local command="${1:-help}"
    shift || true

    case "$command" in
        # Instance info
        list)
            list_instances "$@"
            ;;
        get)
            get_instance "$@"
            ;;

        # Available updates
        list-updates)
            list_available_updates "$@"
            ;;
        list-security)
            list_security_updates "$@"
            ;;
        count)
            count_updates "$@"
            ;;

        # Install updates
        install-all)
            install_all_updates "$@"
            ;;
        install-security)
            install_security_updates "$@"
            ;;
        install-package)
            install_package_update "$@"
            ;;

        # Erratas
        list-erratas)
            list_erratas "$@"
            ;;
        get-errata)
            get_errata "$@"
            ;;
        instance-erratas)
            list_instance_erratas "$@"
            ;;

        # Packages
        list-packages)
            list_installed_packages "$@"
            ;;
        search-packages)
            search_packages "$@"
            ;;

        # Jobs
        list-jobs)
            list_patch_jobs "$@"
            ;;
        get-request)
            get_work_request "$@"
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
