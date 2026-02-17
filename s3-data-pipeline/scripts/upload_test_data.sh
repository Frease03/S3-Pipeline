#!/bin/bash
# Upload test data to the raw bucket to trigger the pipeline

set -e

RAW_BUCKET="${1:-}"

if [ -z "$RAW_BUCKET" ]; then
    echo "Usage: $0 <raw-bucket-name>"
    exit 1
fi

echo "Uploading test data to ${RAW_BUCKET}..."

# Create sample JSON data
cat << 'EOF' > /tmp/test_data.json
[
    {
        "id": "001",
        "name": "Test Record 1",
        "value": 100,
        "timestamp": "2024-01-15T10:30:00Z"
    },
    {
        "id": "002",
        "name": "Test Record 2",
        "value": 200,
        "timestamp": "2024-01-15T11:30:00Z"
    }
]
EOF

# Create sample CSV data
cat << 'EOF' > /tmp/test_data.csv
id,name,value,timestamp
003,Test Record 3,300,2024-01-15T12:30:00Z
004,Test Record 4,400,2024-01-15T13:30:00Z
EOF

# Upload to S3
aws s3 cp /tmp/test_data.json "s3://${RAW_BUCKET}/incoming/test_data.json"
aws s3 cp /tmp/test_data.csv "s3://${RAW_BUCKET}/incoming/test_data.csv"

echo "Test data uploaded successfully!"
echo "Check CloudWatch Logs for Lambda execution details."

# Cleanup
rm /tmp/test_data.json /tmp/test_data.csv
