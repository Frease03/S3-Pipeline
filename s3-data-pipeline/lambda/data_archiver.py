"""
Data Archiver Lambda Function

This Lambda runs on a daily schedule to archive old processed data
to the archive bucket for long-term storage and cost optimization.
"""

import json
import os
import logging
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')

# Environment variables
PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET')
ARCHIVE_BUCKET = os.environ.get('ARCHIVE_BUCKET')
RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', 30))


def handler(event, context):
    """
    Main Lambda handler function.
    
    Scans the processed bucket for files older than RETENTION_DAYS
    and moves them to the archive bucket.
    
    Args:
        event: CloudWatch Events scheduled event
        context: Lambda context object
    
    Returns:
        dict: Archiving result with statistics
    """
    logger.info(f"Starting archival process. Retention: {RETENTION_DAYS} days")
    
    cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    logger.info(f"Archiving files older than: {cutoff_date.isoformat()}")
    
    archived_count = 0
    failed_count = 0
    total_size = 0
    
    # List all objects in the processed bucket
    paginator = s3_client.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=PROCESSED_BUCKET, Prefix='processed/'):
        for obj in page.get('Contents', []):
            key = obj['Key']
            last_modified = obj['LastModified'].replace(tzinfo=None)
            size = obj['Size']
            
            if last_modified < cutoff_date:
                try:
                    archive_file(key, last_modified)
                    archived_count += 1
                    total_size += size
                    logger.info(f"Archived: {key}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to archive {key}: {str(e)}")
    
    result = {
        'statusCode': 200,
        'body': {
            'archived_count': archived_count,
            'failed_count': failed_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        }
    }
    
    logger.info(f"Archival complete: {json.dumps(result['body'])}")
    return result


def archive_file(key: str, last_modified: datetime):
    """
    Archive a single file from processed to archive bucket.
    
    Args:
        key: Object key to archive
        last_modified: Original last modified date
    """
    # Generate archive key with date-based organization
    date_prefix = last_modified.strftime('%Y/%m')
    filename = os.path.basename(key)
    archive_key = f"archive/{date_prefix}/{filename}"
    
    # Copy to archive bucket with metadata
    s3_client.copy_object(
        Bucket=ARCHIVE_BUCKET,
        CopySource={'Bucket': PROCESSED_BUCKET, 'Key': key},
        Key=archive_key,
        Metadata={
            'original_key': key,
            'original_bucket': PROCESSED_BUCKET,
            'archived_at': datetime.utcnow().isoformat(),
            'original_last_modified': last_modified.isoformat()
        },
        MetadataDirective='REPLACE',
        StorageClass='STANDARD_IA'  # Immediate cost savings
    )
    
    # Delete from processed bucket
    s3_client.delete_object(Bucket=PROCESSED_BUCKET, Key=key)


def get_bucket_stats(bucket: str) -> dict:
    """
    Get statistics about a bucket's contents.
    
    Args:
        bucket: S3 bucket name
    
    Returns:
        dict: Bucket statistics
    """
    total_size = 0
    total_count = 0
    
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            total_size += obj['Size']
            total_count += 1
    
    return {
        'bucket': bucket,
        'total_objects': total_count,
        'total_size_bytes': total_size,
        'total_size_mb': round(total_size / (1024 * 1024), 2)
    }
