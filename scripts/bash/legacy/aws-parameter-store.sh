#!/bin/bash
#
# aws-parameter-store.sh - AWS SSM Parameter Store & Secrets Manager (Legacy)
# After Dark Systems - Ops Utils
#
# LEGACY: This script is for AWS. Production uses OCI Vault.
#

set -euo pipefail

AWS_PROFILE="${AWS_PROFILE:-default}"
AWS_REGION="${AWS_REGION:-us-east-1}"

list_parameters() {
    local path="${1:-/}"
    aws ssm get-parameters-by-path \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --path "$path" \
        --recursive \
        --query 'Parameters[*].[Name,Type,LastModifiedDate]' \
        --output table
}

get_parameter() {
    local name="$1"
    aws ssm get-parameter \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --name "$name" \
        --with-decryption \
        --query 'Parameter.Value' \
        --output text
}

put_parameter() {
    local name="$1"
    local value="$2"
    local type="${3:-SecureString}"
    aws ssm put-parameter \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --name "$name" \
        --value "$value" \
        --type "$type" \
        --overwrite
}

list_secrets() {
    aws secretsmanager list-secrets \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --query 'SecretList[*].[Name,Description]' \
        --output table
}

get_secret() {
    local secret_id="$1"
    aws secretsmanager get-secret-value \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --secret-id "$secret_id" \
        --query 'SecretString' \
        --output text
}

usage() {
    cat <<EOF
Usage: $(basename "$0") <command> [options]

AWS Parameter Store & Secrets Manager (Legacy)

Parameter Store:
  list [path]                List parameters
  get <name>                 Get parameter value
  put <name> <value> [type]  Put parameter

Secrets Manager:
  list-secrets               List secrets
  get-secret <id>            Get secret value
EOF
}

main() {
    case "${1:-help}" in
        list) shift; list_parameters "$@" ;;
        get) shift; get_parameter "$@" ;;
        put) shift; put_parameter "$@" ;;
        list-secrets) list_secrets ;;
        get-secret) shift; get_secret "$@" ;;
        *) usage ;;
    esac
}

[[ "${BASH_SOURCE[0]}" == "${0}" ]] && main "$@"
