#!/bin/bash
#
# aws-ssm-session.sh - AWS Systems Manager Session Manager Operations (Legacy)
# After Dark Systems - Ops Utils
#
# LEGACY: This script is for AWS SSM operations. Production uses OCI.
# See ../osm-session.sh for the OCI equivalent.
#

set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SESSION_LOG_DIR="${SESSION_LOG_DIR:-$HOME/.ssm-sessions}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

check_dependencies() {
    for cmd in aws jq; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Missing required dependency: $cmd"
            exit 1
        fi
    done
}

list_instances() {
    aws ssm describe-instance-information \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'InstanceInformationList[*].[InstanceId,PingStatus,PlatformType,ComputerName,IPAddress]' \
        --output table
}

start_session() {
    local instance_id="$1"
    [[ -z "$instance_id" ]] && { log_error "Instance ID required."; exit 1; }
    aws ssm start-session --profile "$AWS_PROFILE" --region "$AWS_REGION" --target "$instance_id"
}

port_forward() {
    local instance_id="$1"
    local remote_port="$2"
    local local_port="${3:-$remote_port}"

    aws ssm start-session \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --target "$instance_id" \
        --document-name AWS-StartPortForwardingSession \
        --parameters "{\"portNumber\":[\"$remote_port\"],\"localPortNumber\":[\"$local_port\"]}"
}

run_command() {
    local instance_ids="$1"
    local command="$2"

    aws ssm send-command \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --instance-ids $instance_ids \
        --document-name "AWS-RunShellScript" \
        --parameters "{\"commands\":[\"$command\"]}" \
        --output json | jq '{CommandId: .Command.CommandId}'
}

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

AWS SSM Session Manager (Legacy)

Commands:
  list                                    List SSM-managed instances
  start <instance_id>                     Start interactive session
  port-forward <instance_id> <port> [local] Port forward
  run <instance_ids> <command>            Run command

Environment:
  AWS_PROFILE, AWS_REGION
EOF
}

main() {
    check_dependencies
    case "${1:-help}" in
        list) list_instances ;;
        start) shift; start_session "$@" ;;
        port-forward) shift; port_forward "$@" ;;
        run) shift; run_command "$@" ;;
        *) usage ;;
    esac
}

[[ "${BASH_SOURCE[0]}" == "${0}" ]] && main "$@"
