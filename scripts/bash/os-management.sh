#!/bin/bash
#
# os-management.sh - OCI OS Management Service Operations
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for OCI OS Management Service
# including managed instance groups, package management, and compliance.
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
# Managed Instance Group Functions
# ============================================================================

# List managed instance groups
list_groups() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing managed instance groups..."

    oci os-management managed-instance-group list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."managed-instance-count")\t\(."lifecycle-state")"'
}

# Get managed instance group details
get_group() {
    local group_id="$1"

    if [[ -z "$group_id" ]]; then
        log_error "Managed instance group OCID required."
        exit 1
    fi

    oci os-management managed-instance-group get \
        --managed-instance-group-id "$group_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# Create managed instance group
create_group() {
    local compartment="${1:-$COMPARTMENT_OCID}"
    local name="$2"
    local description="${3:-}"

    if [[ -z "$compartment" || -z "$name" ]]; then
        log_error "Usage: create-group <compartment> <name> [description]"
        exit 1
    fi

    log_info "Creating managed instance group: $name"

    local cmd="oci os-management managed-instance-group create \
        --compartment-id '$compartment' \
        --display-name '$name' \
        --profile '$OCI_PROFILE'"

    if [[ -n "$description" ]]; then
        cmd="$cmd --description '$description'"
    fi

    eval "$cmd" --output json | jq '.data | {id: .id, name: ."display-name"}'

    log_success "Group created: $name"
}

# Delete managed instance group
delete_group() {
    local group_id="$1"

    if [[ -z "$group_id" ]]; then
        log_error "Group OCID required."
        exit 1
    fi

    log_warn "Deleting managed instance group..."
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci os-management managed-instance-group delete \
        --managed-instance-group-id "$group_id" \
        --profile "$OCI_PROFILE" \
        --force

    log_success "Group deleted"
}

# List instances in group
list_group_instances() {
    local group_id="$1"

    if [[ -z "$group_id" ]]; then
        log_error "Managed instance group OCID required."
        exit 1
    fi

    log_info "Listing instances in group..."

    oci os-management managed-instance-group list-managed-instances \
        --managed-instance-group-id "$group_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")"'
}

# Add instance to group
add_to_group() {
    local group_id="$1"
    local instance_id="$2"

    if [[ -z "$group_id" || -z "$instance_id" ]]; then
        log_error "Usage: add-to-group <group_id> <instance_id>"
        exit 1
    fi

    log_info "Adding instance to group..."

    oci os-management managed-instance-group attach-managed-instance \
        --managed-instance-group-id "$group_id" \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE"

    log_success "Instance added to group"
}

# Remove instance from group
remove_from_group() {
    local group_id="$1"
    local instance_id="$2"

    if [[ -z "$group_id" || -z "$instance_id" ]]; then
        log_error "Usage: remove-from-group <group_id> <instance_id>"
        exit 1
    fi

    log_info "Removing instance from group..."

    oci os-management managed-instance-group detach-managed-instance \
        --managed-instance-group-id "$group_id" \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE"

    log_success "Instance removed from group"
}

# ============================================================================
# Package Management Functions
# ============================================================================

# List installed packages on instance
list_packages() {
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

# Search available packages
search_packages() {
    local compartment="${1:-$COMPARTMENT_OCID}"
    local query="$2"

    if [[ -z "$compartment" || -z "$query" ]]; then
        log_error "Usage: search <compartment> <query>"
        exit 1
    fi

    log_info "Searching packages matching: $query"

    oci os-management software-package search \
        --compartment-id "$compartment" \
        --software-package-name "$query" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(."display-name")\t\(.version)\t\(.type)"'
}

# Install package on instance
install_package() {
    local instance_id="$1"
    local package_name="$2"

    if [[ -z "$instance_id" || -z "$package_name" ]]; then
        log_error "Usage: install <instance_id> <package_name>"
        exit 1
    fi

    log_info "Installing package: $package_name"

    oci os-management managed-instance install-package \
        --managed-instance-id "$instance_id" \
        --software-package-name "$package_name" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'

    log_success "Package installation initiated"
}

# Remove package from instance
remove_package() {
    local instance_id="$1"
    local package_name="$2"

    if [[ -z "$instance_id" || -z "$package_name" ]]; then
        log_error "Usage: remove <instance_id> <package_name>"
        exit 1
    fi

    log_warn "Removing package: $package_name"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci os-management managed-instance remove-package \
        --managed-instance-id "$instance_id" \
        --software-package-name "$package_name" \
        --profile "$OCI_PROFILE"

    log_success "Package removal initiated"
}

# Install packages on group
install_on_group() {
    local group_id="$1"
    local package_name="$2"

    if [[ -z "$group_id" || -z "$package_name" ]]; then
        log_error "Usage: install-on-group <group_id> <package_name>"
        exit 1
    fi

    log_info "Installing package on group: $package_name"

    oci os-management managed-instance-group install-package \
        --managed-instance-group-id "$group_id" \
        --software-package-name "$package_name" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'

    log_success "Group package installation initiated"
}

# ============================================================================
# Software Source Functions
# ============================================================================

# List software sources
list_sources() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing software sources..."

    oci os-management software-source list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."repo-type")\t\(."lifecycle-state")"'
}

# Get software source details
get_source() {
    local source_id="$1"

    if [[ -z "$source_id" ]]; then
        log_error "Software source OCID required."
        exit 1
    fi

    oci os-management software-source get \
        --software-source-id "$source_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# List packages in software source
list_source_packages() {
    local source_id="$1"

    if [[ -z "$source_id" ]]; then
        log_error "Software source OCID required."
        exit 1
    fi

    log_info "Listing packages in software source..."

    oci os-management software-source list-packages \
        --software-source-id "$source_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(."display-name")\t\(.version)"'
}

# ============================================================================
# Scheduled Jobs Functions
# ============================================================================

# List scheduled jobs
list_jobs() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing scheduled jobs..."

    oci os-management scheduled-job list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."operation-type")\t\(."schedule-type")\t\(."lifecycle-state")"'
}

# Get scheduled job details
get_job() {
    local job_id="$1"

    if [[ -z "$job_id" ]]; then
        log_error "Scheduled job OCID required."
        exit 1
    fi

    oci os-management scheduled-job get \
        --scheduled-job-id "$job_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# Run scheduled job now
run_job() {
    local job_id="$1"

    if [[ -z "$job_id" ]]; then
        log_error "Scheduled job OCID required."
        exit 1
    fi

    log_info "Running scheduled job now..."

    oci os-management scheduled-job run-now \
        --scheduled-job-id "$job_id" \
        --profile "$OCI_PROFILE"

    log_success "Scheduled job started"
}

# ============================================================================
# Work Request Functions
# ============================================================================

# List work requests
list_requests() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing work requests..."

    oci os-management work-request list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."operation-type")\t\(.status)\t\(."percent-complete")%"'
}

# Get work request details
get_request() {
    local request_id="$1"

    if [[ -z "$request_id" ]]; then
        log_error "Work request OCID required."
        exit 1
    fi

    oci os-management work-request get \
        --work-request-id "$request_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI OS Management Service Operations

Managed Instance Groups:
  list-groups [compartment]               List managed instance groups
  get-group <group_id>                    Get group details
  create-group <compartment> <name> [desc] Create group
  delete-group <group_id>                 Delete group
  group-instances <group_id>              List instances in group
  add-to-group <group_id> <instance_id>   Add instance to group
  remove-from-group <group_id> <instance> Remove instance from group

Package Management:
  list-packages <instance_id>             List installed packages
  search <compartment> <query>            Search available packages
  install <instance_id> <package>         Install package on instance
  remove <instance_id> <package>          Remove package from instance
  install-on-group <group_id> <package>   Install package on group

Software Sources:
  list-sources [compartment]              List software sources
  get-source <source_id>                  Get source details
  source-packages <source_id>             List packages in source

Scheduled Jobs:
  list-jobs [compartment]                 List scheduled jobs
  get-job <job_id>                        Get job details
  run-job <job_id>                        Run job now

Work Requests:
  list-requests [compartment]             List work requests
  get-request <request_id>                Get request details

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID

Examples:
  $(basename "$0") list-groups
  $(basename "$0") list-packages ocid1.managedinstance.oc1..xxx
  $(basename "$0") install ocid1.managedinstance.oc1..xxx httpd
  $(basename "$0") install-on-group ocid1.managedinstancegroup.oc1..xxx nginx

EOF
}

main() {
    check_dependencies

    local command="${1:-help}"
    shift || true

    case "$command" in
        # Groups
        list-groups)
            list_groups "$@"
            ;;
        get-group)
            get_group "$@"
            ;;
        create-group)
            create_group "$@"
            ;;
        delete-group)
            delete_group "$@"
            ;;
        group-instances)
            list_group_instances "$@"
            ;;
        add-to-group)
            add_to_group "$@"
            ;;
        remove-from-group)
            remove_from_group "$@"
            ;;

        # Packages
        list-packages)
            list_packages "$@"
            ;;
        search)
            search_packages "$@"
            ;;
        install)
            install_package "$@"
            ;;
        remove)
            remove_package "$@"
            ;;
        install-on-group)
            install_on_group "$@"
            ;;

        # Sources
        list-sources)
            list_sources "$@"
            ;;
        get-source)
            get_source "$@"
            ;;
        source-packages)
            list_source_packages "$@"
            ;;

        # Jobs
        list-jobs)
            list_jobs "$@"
            ;;
        get-job)
            get_job "$@"
            ;;
        run-job)
            run_job "$@"
            ;;

        # Work requests
        list-requests)
            list_requests "$@"
            ;;
        get-request)
            get_request "$@"
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
