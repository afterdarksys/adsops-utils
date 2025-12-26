#!/bin/bash
#
# osm-session.sh - OCI OS Management Session & Agent Operations
# After Dark Systems - Ops Utils
#
# This script provides wrapper functions for OCI OS Management Service
# including managed instance sessions, agent management, and run commands.
#

set -euo pipefail

# Configuration
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"
REGION="${OCI_REGION:-}"

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
    if ! oci iam region list --profile "$OCI_PROFILE" &>/dev/null 2>&1; then
        log_error "OCI CLI not configured or session expired for profile: $OCI_PROFILE"
        exit 1
    fi
}

# ============================================================================
# Managed Instance Functions
# ============================================================================

# List all managed instances
list_managed_instances() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required. Set COMPARTMENT_OCID or pass as argument."
        exit 1
    fi

    log_info "Listing managed instances..."

    oci os-management managed-instance list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."display-name")\t\(.status)\t\(."os-family")"'
}

# Get managed instance details
get_managed_instance() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Managed instance OCID required."
        exit 1
    fi

    oci os-management managed-instance get \
        --managed-instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data'
}

# Check agent status on instance
check_agent_status() {
    local instance_id="$1"

    if [[ -z "$instance_id" ]]; then
        log_error "Instance OCID required."
        exit 1
    fi

    log_info "Checking OS Management agent status..."

    oci compute instance get \
        --instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data["agent-config"]'
}

# ============================================================================
# Run Command Functions
# ============================================================================

# Run command on managed instance
run_command() {
    local instance_id="$1"
    local command="$2"
    local timeout="${3:-600}"

    if [[ -z "$instance_id" || -z "$command" ]]; then
        log_error "Usage: run <instance_id> <command> [timeout]"
        exit 1
    fi

    log_info "Running command on instance..."

    # Use instance agent to run command
    oci compute instance-agent command create \
        --compartment-id "$(get_instance_compartment "$instance_id")" \
        --target-instance-id "$instance_id" \
        --execution-time-out-in-seconds "$timeout" \
        --content "{
            \"source\": {
                \"sourceType\": \"TEXT\",
                \"text\": \"$command\"
            },
            \"output\": {
                \"outputType\": \"TEXT\"
            }
        }" \
        --profile "$OCI_PROFILE" \
        --output json | jq '{id: .data.id, state: .data["lifecycle-state"]}'
}

# Get command execution result
get_command_result() {
    local command_id="$1"
    local instance_id="$2"

    if [[ -z "$command_id" || -z "$instance_id" ]]; then
        log_error "Usage: get-result <command_id> <instance_id>"
        exit 1
    fi

    oci compute instance-agent command-execution get \
        --command-id "$command_id" \
        --instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --output json | jq '.data | {
            state: .["lifecycle-state"],
            exitCode: .["exit-code"],
            output: .["content"]["text"]
        }'
}

# Helper to get compartment from instance
get_instance_compartment() {
    local instance_id="$1"
    oci compute instance get \
        --instance-id "$instance_id" \
        --profile "$OCI_PROFILE" \
        --query 'data."compartment-id"' \
        --raw-output
}

# ============================================================================
# Work Request Functions
# ============================================================================

# List work requests
list_work_requests() {
    local compartment="${1:-$COMPARTMENT_OCID}"

    if [[ -z "$compartment" ]]; then
        log_error "Compartment OCID required."
        exit 1
    fi

    log_info "Listing OS Management work requests..."

    oci os-management work-request list \
        --compartment-id "$compartment" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq -r '.data[] | "\(.id)\t\(."operation-type")\t\(.status)\t\(."percent-complete")%"'
}

# Get work request details
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

# Get work request errors
get_work_request_errors() {
    local work_request_id="$1"

    if [[ -z "$work_request_id" ]]; then
        log_error "Work request OCID required."
        exit 1
    fi

    oci os-management work-request-error list \
        --work-request-id "$work_request_id" \
        --profile "$OCI_PROFILE" \
        --all \
        --output json | jq '.data'
}

# ============================================================================
# Software Source Functions
# ============================================================================

# List software sources
list_software_sources() {
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
get_software_source() {
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

# Attach software source to instance
attach_software_source() {
    local instance_id="$1"
    local source_id="$2"

    if [[ -z "$instance_id" || -z "$source_id" ]]; then
        log_error "Usage: attach-source <instance_id> <source_id>"
        exit 1
    fi

    log_info "Attaching software source to instance..."

    oci os-management managed-instance attach-child-software-source \
        --managed-instance-id "$instance_id" \
        --software-source-id "$source_id" \
        --profile "$OCI_PROFILE"

    log_success "Software source attached"
}

# Detach software source from instance
detach_software_source() {
    local instance_id="$1"
    local source_id="$2"

    if [[ -z "$instance_id" || -z "$source_id" ]]; then
        log_error "Usage: detach-source <instance_id> <source_id>"
        exit 1
    fi

    log_info "Detaching software source from instance..."

    oci os-management managed-instance detach-child-software-source \
        --managed-instance-id "$instance_id" \
        --software-source-id "$source_id" \
        --profile "$OCI_PROFILE"

    log_success "Software source detached"
}

# ============================================================================
# Scheduled Job Functions
# ============================================================================

# List scheduled jobs
list_scheduled_jobs() {
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
get_scheduled_job() {
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
run_scheduled_job() {
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
# Main
# ============================================================================

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

OCI OS Management Session & Agent Operations

Managed Instances:
  list [compartment]                      List managed instances
  get <instance_id>                       Get managed instance details
  agent-status <instance_id>              Check OS Management agent status

Run Commands:
  run <instance_id> <command> [timeout]   Run command on instance
  get-result <command_id> <instance_id>   Get command execution result

Work Requests:
  list-requests [compartment]             List work requests
  get-request <work_request_id>           Get work request details
  get-errors <work_request_id>            Get work request errors

Software Sources:
  list-sources [compartment]              List software sources
  get-source <source_id>                  Get software source details
  attach-source <instance_id> <source>    Attach source to instance
  detach-source <instance_id> <source>    Detach source from instance

Scheduled Jobs:
  list-jobs [compartment]                 List scheduled jobs
  get-job <job_id>                        Get job details
  run-job <job_id>                        Run scheduled job now

Environment Variables:
  OCI_PROFILE       OCI CLI profile (default: DEFAULT)
  COMPARTMENT_OCID  Default compartment OCID
  OCI_REGION        OCI region

Examples:
  $(basename "$0") list
  $(basename "$0") get ocid1.managedinstance.oc1..xxx
  $(basename "$0") run ocid1.instance.oc1..xxx "uptime"
  $(basename "$0") list-jobs

EOF
}

main() {
    check_dependencies
    validate_oci_config

    local command="${1:-help}"
    shift || true

    case "$command" in
        # Managed instances
        list)
            list_managed_instances "$@"
            ;;
        get)
            get_managed_instance "$@"
            ;;
        agent-status)
            check_agent_status "$@"
            ;;

        # Run commands
        run)
            run_command "$@"
            ;;
        get-result)
            get_command_result "$@"
            ;;

        # Work requests
        list-requests)
            list_work_requests "$@"
            ;;
        get-request)
            get_work_request "$@"
            ;;
        get-errors)
            get_work_request_errors "$@"
            ;;

        # Software sources
        list-sources)
            list_software_sources "$@"
            ;;
        get-source)
            get_software_source "$@"
            ;;
        attach-source)
            attach_software_source "$@"
            ;;
        detach-source)
            detach_software_source "$@"
            ;;

        # Scheduled jobs
        list-jobs)
            list_scheduled_jobs "$@"
            ;;
        get-job)
            get_scheduled_job "$@"
            ;;
        run-job)
            run_scheduled_job "$@"
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
