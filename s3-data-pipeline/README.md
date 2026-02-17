# S3 Data Pipeline

An automated, serverless data processing pipeline built on AWS that ingests raw data files from S3, processes and transforms them, and manages data lifecycle through archival.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Directory Structure](#directory-structure)
- [Components Explained](#components-explained)
- [Data Flow](#data-flow)
- [Prerequisites](#prerequisites)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Testing](#testing)
- [Monitoring](#monitoring)
- [Cost Optimization](#cost-optimization)
- [Troubleshooting](#troubleshooting)

---

## Overview

This pipeline automates the entire data lifecycle:

1. **Ingest** - Raw data files (JSON/CSV) are uploaded to an S3 bucket
2. **Process** - Lambda functions automatically validate, transform, and enrich the data
3. **Store** - Processed data is stored in a separate bucket with metadata
4. **Archive** - Old data is automatically moved to long-term storage (Glacier)

**Key Features:**
- Fully serverless (no servers to manage)
- Event-driven processing (triggered on file upload)
- Automatic retry with dead-letter queue for failures
- Cost-optimized storage lifecycle management
- Infrastructure as Code with Terraform

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           S3 DATA PIPELINE ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────┐
                                    │   Incoming   │
                                    │    Data      │
                                    └──────┬───────┘
                                           │
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              RAW DATA BUCKET                                  │
│  ┌─────────────────┐                                                         │
│  │ incoming/       │ ──── S3 Event Notification ────┐                        │
│  │   *.json        │                                │                        │
│  │   *.csv         │                                │                        │
│  └─────────────────┘                                │                        │
│  ┌─────────────────┐                                │                        │
│  │ completed/      │ ◄── Files moved here           │                        │
│  │   (processed)   │     after processing           │                        │
│  └─────────────────┘                                │                        │
└─────────────────────────────────────────────────────│────────────────────────┘
                                                      │
                                                      ▼
                                    ┌─────────────────────────────┐
                                    │     DATA PROCESSOR LAMBDA    │
                                    │                              │
                                    │  1. Download file from S3    │
                                    │  2. Validate data structure  │
                                    │  3. Transform & normalize    │
                                    │  4. Add metadata             │
                                    │  5. Upload to processed      │
                                    │  6. Move original to done    │
                                    └──────────────┬──────────────┘
                                                   │
                              ┌────────────────────┴────────────────────┐
                              │                                         │
                              ▼                                         ▼
              ┌───────────────────────────┐             ┌───────────────────────────┐
              │    PROCESSED BUCKET        │             │    SQS DEAD LETTER QUEUE  │
              │                            │             │                           │
              │  processed/                │             │  Failed messages after    │
              │    2024/01/15/             │             │  3 retry attempts         │
              │      data.json             │             │                           │
              └─────────────┬──────────────┘             └───────────────────────────┘
                            │
                            │ After 30 days
                            ▼
              ┌───────────────────────────┐
              │    DATA ARCHIVER LAMBDA    │ ◄── CloudWatch Events (Daily 2AM UTC)
              │                            │
              │  Moves files older than    │
              │  retention period to       │
              │  archive bucket            │
              └─────────────┬──────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │    ARCHIVE BUCKET          │
              │                            │
              │  archive/                  │
              │    2024/01/                │
              │      data.json             │
              │                            │
              │  Lifecycle Policy:         │
              │  - 90 days → Glacier       │
              │  - 365 days → Delete       │
              └───────────────────────────┘
```

---

## How It Works

### Step 1: Data Ingestion

When a file is uploaded to the **raw bucket** under the `incoming/` prefix:

```bash
aws s3 cp data.json s3://raw-bucket/incoming/data.json
```

S3 generates an event notification that triggers the Data Processor Lambda.

### Step 2: Data Processing

The **Data Processor Lambda** performs these operations:

1. **Downloads** the file from S3
2. **Parses** the content (JSON or CSV)
3. **Validates** each record:
   - Removes null/empty values
   - Normalizes field names to lowercase with underscores
4. **Transforms** the data:
   - Adds processing metadata (timestamp, environment, version)
5. **Uploads** the processed data to the processed bucket
6. **Moves** the original file from `incoming/` to `completed/`

**Example Transformation:**

Input (raw):
```json
{"User Name": "John", "Email Address": "john@example.com", "Age": null}
```

Output (processed):
```json
{
  "user_name": "John",
  "email_address": "john@example.com",
  "_metadata": {
    "processed_at": "2024-01-15T10:30:00.000Z",
    "environment": "prod",
    "processor_version": "1.0.0"
  }
}
```

### Step 3: Data Archival

The **Data Archiver Lambda** runs daily at 2 AM UTC and:

1. **Scans** the processed bucket for files older than the retention period (default: 30 days)
2. **Copies** old files to the archive bucket with `STANDARD_IA` storage class
3. **Deletes** the original files from the processed bucket
4. **Logs** statistics about archived data

### Step 4: Glacier Transition

The archive bucket has a **lifecycle policy** that:

- After 90 days: Transitions objects to **Glacier** (very low cost)
- After 365 days: Permanently **deletes** objects

---

## Directory Structure

```
s3-data-pipeline/
├── README.md                 # This documentation
├── config/
│   └── pipeline-config.json  # Pipeline configuration
├── lambda/
│   ├── data_processor.py     # Processes incoming files
│   ├── data_archiver.py      # Archives old processed files
│   └── requirements.txt      # Python dependencies
├── scripts/
│   ├── build_lambdas.sh      # Packages Lambda functions
│   ├── deploy.sh             # Deploys infrastructure
│   └── upload_test_data.sh   # Uploads test files
└── terraform/
    ├── main.tf               # S3 buckets, SQS, notifications
    ├── lambda.tf             # Lambda functions and IAM
    ├── variables.tf          # Input variables
    ├── outputs.tf            # Output values
    └── terraform.tfvars.example
```

---

## Components Explained

### S3 Buckets

| Bucket | Purpose | Key Features |
|--------|---------|--------------|
| **Raw** | Landing zone for incoming data | Versioning enabled, event notifications |
| **Processed** | Stores transformed data | Versioning enabled, organized by date |
| **Archive** | Long-term storage | Lifecycle policy for Glacier transition |

### Lambda Functions

| Function | Trigger | Purpose |
|----------|---------|---------|
| **data_processor** | S3 PutObject event | Validates and transforms incoming data |
| **data_archiver** | CloudWatch Events (daily) | Moves old data to archive |

### SQS Queues

| Queue | Purpose |
|-------|---------|
| **Processing Queue** | Buffer for high-volume processing (optional) |
| **Dead Letter Queue** | Captures failed messages after 3 retries |

### IAM Roles

The Lambda execution role has permissions to:
- Read/write all three S3 buckets
- Write to CloudWatch Logs
- Send messages to SQS queues

---

## Data Flow

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌─────────┐
│  Upload  │───►│   Raw    │───►│ Processor │───►│Processed│
│  File    │    │  Bucket  │    │  Lambda   │    │ Bucket  │
└──────────┘    └──────────┘    └───────────┘    └────┬────┘
                                                      │
                                                      │ 30 days
                                                      ▼
                                               ┌─────────────┐
                                               │  Archiver   │
                                               │   Lambda    │
                                               └──────┬──────┘
                                                      │
                                                      ▼
                                               ┌─────────────┐
                                               │   Archive   │──► Glacier (90d)
                                               │   Bucket    │──► Delete (365d)
                                               └─────────────┘
```

---

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0.0
- Python 3.11 (for Lambda development)
- Bash (for deployment scripts)

---

## Deployment

### 1. Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 2. Build and Deploy

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy everything
./scripts/deploy.sh
```

### 3. Manual Deployment

```bash
# Build Lambda packages
./scripts/build_lambdas.sh

# Deploy with Terraform
cd terraform
terraform init
terraform plan
terraform apply
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RETENTION_DAYS` | Days before archiving | 30 |
| `ARCHIVE_DAYS` | Days before Glacier | 90 |
| `ENVIRONMENT` | Environment name | dev |

### Terraform Variables

```hcl
# terraform.tfvars
aws_region            = "us-east-1"
environment           = "prod"
raw_bucket_name       = "mycompany-raw-data-prod"
processed_bucket_name = "mycompany-processed-data-prod"
archive_bucket_name   = "mycompany-archive-data-prod"
retention_days        = 30
archive_days          = 90
```

---

## Testing

### Upload Test Data

```bash
./scripts/upload_test_data.sh <raw-bucket-name>
```

### Verify Processing

```bash
# Check processed bucket
aws s3 ls s3://<processed-bucket>/processed/ --recursive

# Check Lambda logs
aws logs tail /aws/lambda/<function-name> --follow
```

---

## Monitoring

### CloudWatch Metrics to Monitor

- **Lambda Invocations** - Number of files processed
- **Lambda Errors** - Processing failures
- **Lambda Duration** - Processing time
- **SQS DLQ Messages** - Failed processing attempts

### CloudWatch Alarms (Recommended)

```hcl
# Add to terraform/main.tf for production
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "data-processor-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

---

## Cost Optimization

This pipeline is designed for cost efficiency:

| Component | Cost Optimization |
|-----------|-------------------|
| **Lambda** | Pay only for execution time |
| **S3 Standard** | Used for active data (raw/processed) |
| **S3 Standard-IA** | Used for archived data (immediate savings) |
| **S3 Glacier** | Used for long-term storage (90+ days) |
| **Auto-deletion** | Data deleted after 365 days |

**Estimated Monthly Cost** (10GB data/month):
- S3 Storage: ~$2-5
- Lambda: ~$1-2
- Data Transfer: ~$1
- **Total: ~$5-10/month**

---

## Troubleshooting

### File Not Processing

1. Check file is in `incoming/` prefix
2. Verify file extension is `.json` or `.csv`
3. Check Lambda CloudWatch logs for errors

### Processing Errors

1. Check Dead Letter Queue for failed messages
2. Review Lambda error logs
3. Validate input file format

### Archiver Not Running

1. Verify CloudWatch Events rule is enabled
2. Check Lambda execution role permissions
3. Review archiver Lambda logs

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AccessDenied` | IAM permissions | Check Lambda role policy |
| `NoSuchKey` | File moved/deleted | Check S3 event timing |
| `JSONDecodeError` | Invalid JSON | Validate input file format |

---

## License

MIT License - See LICENSE file for details.
