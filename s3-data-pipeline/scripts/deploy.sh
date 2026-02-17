#!/bin/bash
# Deploy S3 Data Pipeline infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/.."
TERRAFORM_DIR="${PROJECT_DIR}/terraform"

# Default values
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "=========================================="
echo "S3 Data Pipeline Deployment"
echo "Environment: ${ENVIRONMENT}"
echo "Region: ${AWS_REGION}"
echo "=========================================="

# Build Lambda packages first
echo "Step 1: Building Lambda packages..."
"${SCRIPT_DIR}/build_lambdas.sh"

# Initialize and apply Terraform
echo "Step 2: Deploying infrastructure with Terraform..."
cd "${TERRAFORM_DIR}"

terraform init

terraform plan \
    -var="environment=${ENVIRONMENT}" \
    -var="aws_region=${AWS_REGION}" \
    -out=tfplan

read -p "Do you want to apply this plan? (yes/no): " confirm
if [ "$confirm" = "yes" ]; then
    terraform apply tfplan
    echo "Deployment complete!"
    echo ""
    echo "Outputs:"
    terraform output
else
    echo "Deployment cancelled."
fi
