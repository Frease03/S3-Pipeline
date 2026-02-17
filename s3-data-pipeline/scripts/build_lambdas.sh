#!/bin/bash
# Build Lambda deployment packages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="${SCRIPT_DIR}/../lambda"
BUILD_DIR="${SCRIPT_DIR}/../build"

echo "Building Lambda deployment packages..."

# Clean and create build directory
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Build data_processor.zip
echo "Building data_processor.zip..."
cd "${LAMBDA_DIR}"
zip -j "${BUILD_DIR}/data_processor.zip" data_processor.py
cp "${BUILD_DIR}/data_processor.zip" "${LAMBDA_DIR}/data_processor.zip"

# Build data_archiver.zip
echo "Building data_archiver.zip..."
zip -j "${BUILD_DIR}/data_archiver.zip" data_archiver.py
cp "${BUILD_DIR}/data_archiver.zip" "${LAMBDA_DIR}/data_archiver.zip"

echo "Build complete!"
echo "Packages created:"
ls -la "${LAMBDA_DIR}"/*.zip
