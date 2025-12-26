#!/bin/bash
#
# parameter-store.sh - OCI Vault Secrets Management
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for OCI Vault service
# including secrets management, key management, and secret versions.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"
VAULT_OCID="${VAULT_OCID:-}"
KEY_OCID="${KEY_OCID:-}"

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
    for cmd in oci jq base64; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Missing required dependency: $cmd"
            exit 1
        fi
    done
}

# ============================================================================
# Vault Functions
# ============================================================================

# List vaults in compartment
list_vaults() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing vaults..."

    oci kms management vault list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(."vault-type")\t\(."lifecycle-state")"'
}

# Get vault details
get_vault() {
    local vault_id="${1:-$VAULT_OCID}"

    if [[ -z "$vault_id" ]]; then
        log_error "Vault OCID required."
        exit 1
    fi

    oci kms management vault get \
        --vault-id "$vault_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            id: .id,
            displayName: ."display-name",
            vaultType: ."vault-type",
            cryptoEndpoint: ."crypto-endpoint",
            managementEndpoint: ."management-endpoint",
            state: ."lifecycle-state"
        }'
}

# ============================================================================
# Key Functions
# ============================================================================

# List keys in vault
list_keys() {
    local compartment="${1:-$COMPARTMENT_OCID}"
    local vault_id="${2:-$VAULT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing keys..."

    # Get management endpoint
    local mgmt_endpoint
    if [[ -n "$vault_id" ]]; then
        mgmt_endpoint=$(oci kms management vault get \
            --vault-id "$vault_id" \
            --profile "$OCI_PROFILE" \
            --query 'data."management-endpoint"' \
            --raw-output)

        oci kms management key list \
            --compartment-id "$compartment" \
            --endpoint "$mgmt_endpoint" \
            --profile "$OCI_PROFILE" \
            --all \
            --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(.algorithm)\t\(."lifecycle-state")"'
    else
        log_error "Vault OCID required for listing keys."
        exit 1
    fi
}

# Get key details
get_key() {
    local key_id="$1"
    local vault_id="${2:-$VAULT_OCID}"

    if [[ -z "$key_id" || -z "$vault_id" ]]; then
        log_error "Usage: get-key <key_id> [vault_id]"
        exit 1
    fi

    local mgmt_endpoint
    mgmt_endpoint=$(oci kms management vault get \
        --vault-id "$vault_id" \
        --profile "$OCI_PROFILE" \
        --query 'data."management-endpoint"' \
        --raw-output)

    oci kms management key get \
        --key-id "$key_id" \
        --endpoint "$mgmt_endpoint" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# ============================================================================
# Secret Functions
# ============================================================================

# List secrets in vault
list_secrets() {
    local compartment="${1:-$COMPARTMENT_OCID}"
    local vault_id="${2:-$VAULT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing secrets..."

    if [[ -n "$vault_id" ]]; then
        oci vault secret list \
            --compartment-id "$compartment" \
            --vault-id "$vault_id" \
            --profile "$OCI_PROFILE" \
            --all \
            --output json | jq -r '.data[] | "\(.id)\t\(."secret-name")\t\(."lifecycle-state")"'
    else
        oci vault secret list \
            --compartment-id "$compartment" \
            --profile "$OCI_PROFILE" \
            --all \
            --output json | jq -r '.data[] | "\(.id)\t\(."secret-name")\t\(."lifecycle-state")"'
    fi
}

# Get secret metadata
get_secret_metadata() {
    local secret_id="$1"

    if [[ -z "$secret_id" ]]; then
        log_error "Secret OCID required."
        exit 1
    fi

    oci vault secret get \
        --secret-id "$secret_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            id: .id,
            secretName: ."secret-name",
            currentVersionNumber: ."current-version-number",
            state: ."lifecycle-state",
            vaultId: ."vault-id",
            keyId: ."key-id"
        }'
}

# Get secret value (current version)
get_secret() {
    local secret_id="$1"

    if [[ -z "$secret_id" ]]; then
        log_error "Secret OCID required."
        exit 1
    fi

    # Get the secret bundle (current version)
    local bundle
    bundle=$(oci secrets secret-bundle get \
        --secret-id "$secret_id" \
        --profile "$OCI_PROFILE" \
        --output json)

    # Decode base64 content
    echo "$bundle" | jq -r '.data["secret-bundle-content"].content' | base64 -d
}

# Get secret value by version
get_secret_version() {
    local secret_id="$1"
    local version="${2:-}"

    if [[ -z "$secret_id" ]]; then
        log_error "Secret OCID required."
        exit 1
    fi

    local bundle
    if [[ -n "$version" ]]; then
        bundle=$(oci secrets secret-bundle get \
            --secret-id "$secret_id" \
            --version-number "$version" \
            --profile "$OCI_PROFILE" \
            --output json)
    else
        bundle=$(oci secrets secret-bundle get \
            --secret-id "$secret_id" \
            --profile "$OCI_PROFILE" \
            --output json)
    fi

    echo "$bundle" | jq -r '.data["secret-bundle-content"].content' | base64 -d
}

# Create new secret
create_secret() {
    local compartment="${1:-$COMPARTMENT_OCID}"
    local vault_id="${2:-$VAULT_OCID}"
    local key_id="${3:-$KEY_OCID}"
    local name="$4"
    local value="$5"
    local description="${6:-}"

    if [[ -z "$compartment" || -z "$vault_id" || -z "$key_id" || -z "$name" || -z "$value" ]]; then
        log_error "Usage: create <compartment> <vault_id> <key_id> <name> <value> [description]"
        exit 1
    fi

    # Base64 encode the value
    local encoded_value
    encoded_value=$(echo -n "$value" | base64)

    log_info "Creating secret: $name"

    local cmd="oci vault secret create-base64 \
        --compartment-id '$compartment' \
        --vault-id '$vault_id' \
        --key-id '$key_id' \
        --secret-name '$name' \
        --secret-content-content '$encoded_value' \
        --profile '$OCI_PROFILE'"

    if [[ -n "$description" ]]; then
        cmd="$cmd --description '$description'"
    fi

    eval "$cmd" --output json | jq '.data | {id: .id, name: ."secret-name"}'

    log_success "Secret created: $name"
}

# Update secret (create new version)
update_secret() {
    local secret_id="$1"
    local value="$2"

    if [[ -z "$secret_id" || -z "$value" ]]; then
        log_error "Usage: update <secret_id> <value>"
        exit 1
    fi

    # Base64 encode the value
    local encoded_value
    encoded_value=$(echo -n "$value" | base64)

    log_info "Updating secret..."

    oci vault secret update-base64 \
        --secret-id "$secret_id" \
        --secret-content-content "$encoded_value" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {id: .id, name: ."secret-name"}'

    log_success "Secret updated"
}

# Delete (schedule deletion of) secret
delete_secret() {
    local secret_id="$1"
    local days="${2:-30}"  # Default 30 days pending deletion

    if [[ -z "$secret_id" ]]; then
        log_error "Secret OCID required."
        exit 1
    fi

    log_warn "Scheduling secret for deletion in $days days"
    read -p "Continue? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    oci vault secret schedule-secret-deletion \
        --secret-id "$secret_id" \
        --time-of-deletion "$(date -v+${days}d -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -d "+${days} days" -u +%Y-%m-%dT%H:%M:%SZ)" \
        --profile "$OCI_PROFILE"

    log_success "Secret scheduled for deletion"
}

# Cancel deletion
cancel_deletion() {
    local secret_id="$1"

    if [[ -z "$secret_id" ]]; then
        log_error "Secret OCID required."
        exit 1
    fi

    oci vault secret cancel-secret-deletion \
        --secret-id "$secret_id" \
        --profile "$OCI_PROFILE"

    log_success "Secret deletion cancelled"
}

# ============================================================================
# Secret Version Functions
# ============================================================================

# List secret versions
list_versions() {
    local secret_id="$1"

    if [[ -z "$secret_id" ]]; then
        log_error "Secret OCID required."
        exit 1
    fi

    log_info "Listing secret versions..."

    oci vault secret-version list \
        --secret-id "$secret_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(."version-number")\t\(.stages[])\t\(."time-created")"'
}

# Rotate secret (create new version and deprecate old)
rotate_secret() {
    local secret_id="$1"
    local new_value="$2"

    if [[ -z "$secret_id" || -z "$new_value" ]]; then
        log_error "Usage: rotate <secret_id> <new_value>"
        exit 1
    fi

    log_info "Rotating secret..."

    # Get current version
    local current_version
    current_version=$(oci vault secret get \
        --secret-id "$secret_id" \
        --profile "$OCI_PROFILE" \
        --query 'data."current-version-number"' \
        --raw-output)

    # Create new version
    update_secret "$secret_id" "$new_value"

    log_success "Secret rotated. Previous version: $current_version"
}

# ============================================================================
# Utility Functions
# ============================================================================

# Export secrets to JSON file (without values, just metadata)
export_metadata() {
    local compartment="${1:-$COMPARTMENT_OCID}"
    local output_file="${2:-secrets-metadata.json}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Exporting secrets metadata..."

    oci vault secret list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq '.data | map({id: .id, name: ."secret-name", state: ."lifecycle-state", vaultId: ."vault-id"})' > "$output_file"

    log_success "Metadata exported to: $output_file"
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI Vault Secrets Management

Vaults:
  list-vaults [compartment]               List vaults
  get-vault [vault_id]                    Get vault details

Keys:
  list-keys [compartment] [vault_id]      List keys in vault
  get-key <key_id> [vault_id]             Get key details

Secrets:
  list [compartment] [vault_id]           List secrets
  get-metadata <secret_id>                Get secret metadata
  get <secret_id>                         Get secret value
  get-version <secret_id> [version]       Get specific version value

  create <comp> <vault> <key> <name> <value> [desc]
                                          Create new secret
  update <secret_id> <value>              Update secret (new version)
  delete <secret_id> [days]               Schedule secret deletion
  cancel-deletion <secret_id>             Cancel pending deletion

Versions:
  list-versions <secret_id>               List secret versions
  rotate <secret_id> <new_value>          Rotate secret

Utilities:
  export-metadata [compartment] [file]    Export secrets metadata

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
  VAULT_OCID        Default vault OCID
  KEY_OCID          Default encryption key OCID

Examples:
  $(basename "$0") list-vaults
  $(basename "$0") list
  $(basename "$0") get ocid1.vaultsecret.oc1..xxx
  $(basename "$0") create "\$COMPARTMENT" "\$VAULT" "\$KEY" "db-password" "secret123"
  $(basename "$0") rotate ocid1.vaultsecret.oc1..xxx "new-secret-value"

EOF
}

main() {
    check_dependencies

    local command="${1:-help}"
    shift || true

    case "$command" in
        # Vaults
        list-vaults)
            list_vaults "$@"
            ;;
        get-vault)
            get_vault "$@"
            ;;

        # Keys
        list-keys)
            list_keys "$@"
            ;;
        get-key)
            get_key "$@"
            ;;

        # Secrets
        list)
            list_secrets "$@"
            ;;
        get-metadata)
            get_secret_metadata "$@"
            ;;
        get)
            get_secret "$@"
            ;;
        get-version)
            get_secret_version "$@"
            ;;
        create)
            create_secret "$@"
            ;;
        update)
            update_secret "$@"
            ;;
        delete)
            delete_secret "$@"
            ;;
        cancel-deletion)
            cancel_deletion "$@"
            ;;

        # Versions
        list-versions)
            list_versions "$@"
            ;;
        rotate)
            rotate_secret "$@"
            ;;

        # Utilities
        export-metadata)
            export_metadata "$@"
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
