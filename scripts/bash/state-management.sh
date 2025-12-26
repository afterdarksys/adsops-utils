#!/bin/bash
#
# state-management.sh - OCI Object Storage State Management for Terraform
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for managing Terraform state
# stored in OCI Object Storage, including state locking and migrations.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
NAMESPACE="${NAMESPACE:-}"
STATE_BUCKET="${STATE_BUCKET:-terraform-state}"
LOCK_BUCKET="${LOCK_BUCKET:-terraform-locks}"
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
    for cmd in oci jq terraform; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Missing required dependency: $cmd"
            exit 1
        fi
    done
}

# Get namespace if not set
get_namespace() {
    if [[ -z "$NAMESPACE" ]]; then
        NAMESPACE=$(oci os ns get --profile "$OCI_PROFILE" --query 'data' --raw-output)
    fi
    echo "$NAMESPACE"
}

# ============================================================================
# Object Storage State Backend Functions
# ============================================================================

# List state files in bucket
list_states() {
    local bucket="${1:-$STATE_BUCKET}"
    local prefix="${2:-}"

    local ns
    ns=$(get_namespace)

    log_info "Listing state files in $ns/$bucket/$prefix"

    oci os object list \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --prefix "$prefix" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | select(.name | endswith(".tfstate")) | "\(.name)\t\(.size)\t\(."time-modified")"'
}

# Get state file content
get_state() {
    local key="$1"
    local output="${2:-}"
    local bucket="${3:-$STATE_BUCKET}"

    if [[ -z "$key" ]]; then
        log_error "Usage: get <key> [output_file] [bucket]"
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    if [[ -n "$output" ]]; then
        oci os object get \
            --namespace-name "$ns" \
            --bucket-name "$bucket" \
            --name "$key" \
            --file "$output" \
            --profile "$OCI_PROFILE"
        log_success "State downloaded to: $output"
    else
        oci os object get \
            --namespace-name "$ns" \
            --bucket-name "$bucket" \
            --name "$key" \
            --file /dev/stdout \
            --profile "$OCI_PROFILE"
    fi
}

# Upload state file
put_state() {
    local key="$1"
    local file="$2"
    local bucket="${3:-$STATE_BUCKET}"

    if [[ -z "$key" || -z "$file" ]]; then
        log_error "Usage: put <key> <file> [bucket]"
        exit 1
    fi

    if [[ ! -f "$file" ]]; then
        log_error "File not found: $file"
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    log_warn "Uploading state to $ns/$bucket/$key"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci os object put \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --name "$key" \
        --file "$file" \
        --profile "$OCI_PROFILE" \
        --force

    log_success "State uploaded"
}

# Delete state file
delete_state() {
    local key="$1"
    local bucket="${2:-$STATE_BUCKET}"

    if [[ -z "$key" ]]; then
        log_error "Usage: delete <key> [bucket]"
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    log_warn "Deleting state: $ns/$bucket/$key"
    read -p "This is permanent! Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci os object delete \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --name "$key" \
        --profile "$OCI_PROFILE" \
        --force

    log_success "State deleted"
}

# List state versions (object versioning)
list_versions() {
    local key="$1"
    local bucket="${2:-$STATE_BUCKET}"

    if [[ -z "$key" ]]; then
        log_error "Usage: list-versions <key> [bucket]"
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    log_info "Listing versions for: $ns/$bucket/$key"

    oci os object-version list \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --prefix "$key" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(."version-id")\t\(.size)\t\(."time-modified")"'
}

# Restore state from version
restore_version() {
    local key="$1"
    local version_id="$2"
    local bucket="${3:-$STATE_BUCKET}"

    if [[ -z "$key" || -z "$version_id" ]]; then
        log_error "Usage: restore <key> <version_id> [bucket]"
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    log_warn "Restoring $ns/$bucket/$key from version $version_id"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    # Download version to temp file
    local temp_file
    temp_file=$(mktemp)

    oci os object get \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --name "$key" \
        --version-id "$version_id" \
        --file "$temp_file" \
        --profile "$OCI_PROFILE"

    # Upload as current version
    oci os object put \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --name "$key" \
        --file "$temp_file" \
        --profile "$OCI_PROFILE" \
        --force

    rm -f "$temp_file"

    log_success "State restored from version: $version_id"
}

# ============================================================================
# Lock Functions (using separate bucket or objects)
# ============================================================================

# List locks
list_locks() {
    local bucket="${1:-$LOCK_BUCKET}"

    local ns
    ns=$(get_namespace)

    log_info "Listing state locks in $ns/$bucket"

    oci os object list \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | select(.name | endswith(".lock")) | "\(.name)\t\(.size)\t\(."time-modified")"'
}

# Check if state is locked
check_lock() {
    local state_key="$1"
    local bucket="${2:-$LOCK_BUCKET}"

    if [[ -z "$state_key" ]]; then
        log_error "State key required."
        exit 1
    fi

    local ns
    ns=$(get_namespace)
    local lock_key="${state_key}.lock"

    if oci os object head \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --name "$lock_key" \
        --profile "$OCI_PROFILE" &>/dev/null; then

        log_warn "State is LOCKED"
        oci os object get \
            --namespace-name "$ns" \
            --bucket-name "$bucket" \
            --name "$lock_key" \
            --file /dev/stdout \
            --profile "$OCI_PROFILE" 2>/dev/null | jq '.'
        return 1
    else
        log_success "State is unlocked"
        return 0
    fi
}

# Force unlock state
force_unlock() {
    local state_key="$1"
    local bucket="${2:-$LOCK_BUCKET}"

    if [[ -z "$state_key" ]]; then
        log_error "State key required."
        exit 1
    fi

    local ns
    ns=$(get_namespace)
    local lock_key="${state_key}.lock"

    log_warn "Force unlocking: $lock_key"
    read -p "This is dangerous! Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci os object delete \
        --namespace-name "$ns" \
        --bucket-name "$bucket" \
        --name "$lock_key" \
        --profile "$OCI_PROFILE" \
        --force

    log_success "Lock removed"
}

# ============================================================================
# Terraform State Operations
# ============================================================================

# Show terraform state
tf_state_list() {
    terraform state list
}

# Show specific resource
tf_state_show() {
    local resource="$1"

    if [[ -z "$resource" ]]; then
        log_error "Resource address required."
        exit 1
    fi

    terraform state show "$resource"
}

# Move resource in state
tf_state_mv() {
    local source="$1"
    local destination="$2"

    if [[ -z "$source" || -z "$destination" ]]; then
        log_error "Usage: tf-mv <source> <destination>"
        exit 1
    fi

    log_warn "Moving state: $source -> $destination"
    terraform state mv "$source" "$destination"
    log_success "State moved"
}

# Remove resource from state
tf_state_rm() {
    local resource="$1"

    if [[ -z "$resource" ]]; then
        log_error "Resource address required."
        exit 1
    fi

    log_warn "Removing from state: $resource"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    terraform state rm "$resource"
    log_success "Resource removed from state"
}

# Import resource into state
tf_state_import() {
    local resource="$1"
    local id="$2"

    if [[ -z "$resource" || -z "$id" ]]; then
        log_error "Usage: tf-import <resource_address> <resource_id>"
        exit 1
    fi

    log_info "Importing: $resource = $id"
    terraform import "$resource" "$id"
    log_success "Resource imported"
}

# Pull remote state to local
tf_state_pull() {
    local output="${1:-terraform.tfstate.backup}"

    terraform state pull > "$output"
    log_success "State pulled to: $output"
}

# Push local state to remote
tf_state_push() {
    local file="${1:-terraform.tfstate}"

    if [[ ! -f "$file" ]]; then
        log_error "State file not found: $file"
        exit 1
    fi

    log_warn "Pushing state from: $file"
    read -p "This is dangerous! Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    terraform state push "$file"
    log_success "State pushed"
}

# Refresh state
tf_refresh() {
    log_info "Refreshing state..."
    terraform refresh
    log_success "State refreshed"
}

# ============================================================================
# Bucket Management
# ============================================================================

# Create state bucket with versioning
create_state_bucket() {
    local bucket="${1:-$STATE_BUCKET}"
    local compartment="${2:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    log_info "Creating state bucket: $ns/$bucket"

    oci os bucket create \
        --namespace-name "$ns" \
        --compartment-id "$compartment" \
        --name "$bucket" \
        --versioning Enabled \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {name: .name, namespace: .namespace, versioning: .versioning}'

    log_success "Bucket created with versioning enabled"
}

# Create lock bucket
create_lock_bucket() {
    local bucket="${1:-$LOCK_BUCKET}"
    local compartment="${2:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    local ns
    ns=$(get_namespace)

    log_info "Creating lock bucket: $ns/$bucket"

    oci os bucket create \
        --namespace-name "$ns" \
        --compartment-id "$compartment" \
        --name "$bucket" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {name: .name, namespace: .namespace}'

    log_success "Lock bucket created"
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI Object Storage State Management for Terraform

State Files:
  list [bucket] [prefix]                  List state files
  get <key> [output_file] [bucket]        Download state file
  put <key> <file> [bucket]               Upload state file
  delete <key> [bucket]                   Delete state file
  list-versions <key> [bucket]            List state versions
  restore <key> <version_id> [bucket]     Restore from version

Locks:
  list-locks [bucket]                     List state locks
  check-lock <state_key> [bucket]         Check if state is locked
  force-unlock <state_key> [bucket]       Force unlock state

Terraform State Operations:
  tf-list                                 List resources in state
  tf-show <resource>                      Show resource details
  tf-mv <source> <destination>            Move resource in state
  tf-rm <resource>                        Remove resource from state
  tf-import <resource> <id>               Import resource into state
  tf-pull [output_file]                   Pull remote state to local
  tf-push [state_file]                    Push local state to remote
  tf-refresh                              Refresh state

Bucket Setup:
  create-bucket [bucket] [compartment]    Create state bucket with versioning
  create-lock-bucket [bucket] [compartment]
                                          Create lock bucket

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  NAMESPACE         OCI namespace (auto-detected if not set)
  STATE_BUCKET      State bucket name (default: terraform-state)
  LOCK_BUCKET       Lock bucket name (default: terraform-locks)
  COMPARTMENT_OCID  Default compartment OCID

Examples:
  $(basename "$0") list
  $(basename "$0") get prod/terraform.tfstate state.json
  $(basename "$0") check-lock prod/terraform.tfstate
  $(basename "$0") tf-list
  $(basename "$0") tf-show oci_core_instance.web

EOF
}

main() {
    check_dependencies

    local command="${1:-help}"
    shift || true

    case "$command" in
        # State files
        list)
            list_states "$@"
            ;;
        get)
            get_state "$@"
            ;;
        put)
            put_state "$@"
            ;;
        delete)
            delete_state "$@"
            ;;
        list-versions)
            list_versions "$@"
            ;;
        restore)
            restore_version "$@"
            ;;

        # Locks
        list-locks)
            list_locks "$@"
            ;;
        check-lock)
            check_lock "$@"
            ;;
        force-unlock)
            force_unlock "$@"
            ;;

        # Terraform state
        tf-list)
            tf_state_list "$@"
            ;;
        tf-show)
            tf_state_show "$@"
            ;;
        tf-mv)
            tf_state_mv "$@"
            ;;
        tf-rm)
            tf_state_rm "$@"
            ;;
        tf-import)
            tf_state_import "$@"
            ;;
        tf-pull)
            tf_state_pull "$@"
            ;;
        tf-push)
            tf_state_push "$@"
            ;;
        tf-refresh)
            tf_refresh "$@"
            ;;

        # Bucket setup
        create-bucket)
            create_state_bucket "$@"
            ;;
        create-lock-bucket)
            create_lock_bucket "$@"
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
