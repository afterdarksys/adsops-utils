#!/bin/bash
#
# aws-patch-management.sh - AWS SSM Patch Manager (Legacy)
# After Dark Systems - Ops Utils
#
# LEGACY: This script is for AWS Patch Manager. Production uses OCI OS Management.
#

set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-us-east-1}"

log_info() { echo -e "\033[0;34m[INFO]\033[0m $*"; }

list_baselines() {
    aws ssm describe-patch-baselines \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'BaselineIdentities[*].[BaselineId,BaselineName,OperatingSystem]' \
        --output table
}

get_patch_states() {
    aws ssm describe-instance-patch-states \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --output json | jq '.InstancePatchStates[] | {InstanceId, InstalledCount, MissingCount, FailedCount}'
}

scan_patches() {
    local instance_ids="$1"
    aws ssm send-command \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --document-name "AWS-RunPatchBaseline" \
        --instance-ids $instance_ids \
        --parameters '{"Operation":["Scan"]}' \
        --output json | jq '{CommandId: .Command.CommandId}'
}

install_patches() {
    local instance_ids="$1"
    aws ssm send-command \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --document-name "AWS-RunPatchBaseline" \
        --instance-ids $instance_ids \
        --parameters '{"Operation":["Install"]}' \
        --output json | jq '{CommandId: .Command.CommandId}'
}

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

AWS Patch Manager (Legacy)

Commands:
  list-baselines          List patch baselines
  get-states              Get patch compliance states
  scan <instance_ids>     Scan for patches
  install <instance_ids>  Install patches
EOF
}

main() {
    case "${1:-help}" in
        list-baselines) list_baselines ;;
        get-states) get_patch_states ;;
        scan) shift; scan_patches "$@" ;;
        install) shift; install_patches "$@" ;;
        *) usage ;;
    esac
}

[[ "${BASH_SOURCE[0]}" == "${0}" ]] && main "$@"
