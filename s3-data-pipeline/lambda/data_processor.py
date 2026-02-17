"""
Data Processor Lambda Function

This Lambda is triggered when new files are uploaded to the raw S3 bucket.
It processes incoming JSON/CSV files, validates data, transforms it,
and stores the results in the processed bucket.
"""

import json
import csv
import os
import logging
from datetime import datetime
from io import StringIO
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')

# Environment variables
RAW_BUCKET = os.environ.get('RAW_BUCKET')
PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')


def handler(event, context):
    """
    Main Lambda handler function.
    
    Args:
        event: S3 event notification containing bucket and object information
        context: Lambda context object
    
    Returns:
        dict: Processing result with status and details
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    processed_files = []
    failed_files = []
    
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        try:
            result = process_file(bucket, key)
            processed_files.append({
                'source_key': key,
                'destination_key': result['destination_key'],
                'records_processed': result['records_processed']
            })
            logger.info(f"Successfully processed: {key}")
            
        except Exception as e:
            logger.error(f"Failed to process {key}: {str(e)}")
            failed_files.append({
                'source_key': key,
                'error': str(e)
            })
    
    return {
        'statusCode': 200,
        'body': {
            'processed': processed_files,
            'failed': failed_files,
            'timestamp': datetime.utcnow().isoformat()
        }
    }


def process_file(bucket: str, key: str) -> dict:
    """
    Process a single file from S3.
    
    Args:
        bucket: Source S3 bucket name
        key: Object key in the bucket
    
    Returns:
        dict: Processing result with destination key and record count
    """
    # Download file from S3
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    
    # Determine file type and process accordingly
    if key.endswith('.json'):
        processed_data, record_count = process_json(content)
    elif key.endswith('.csv'):
        processed_data, record_count = process_csv(content)
    else:
        raise ValueError(f"Unsupported file type: {key}")
    
    # Generate destination key with timestamp
    timestamp = datetime.utcnow().strftime('%Y/%m/%d/%H%M%S')
    filename = os.path.basename(key)
    destination_key = f"processed/{timestamp}/{filename}"
    
    # Upload processed data to processed bucket
    s3_client.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=destination_key,
        Body=processed_data,
        ContentType='application/json',
        Metadata={
            'source_bucket': bucket,
            'source_key': key,
            'processed_at': datetime.utcnow().isoformat(),
            'record_count': str(record_count)
        }
    )
    
    # Move original file to processed folder in raw bucket
    move_to_processed(bucket, key)
    
    return {
        'destination_key': destination_key,
        'records_processed': record_count
    }


def process_json(content: str) -> tuple:
    """
    Process JSON content: validate, transform, and enrich data.
    
    Args:
        content: Raw JSON string
    
    Returns:
        tuple: (processed JSON string, record count)
    """
    data = json.loads(content)
    
    # Handle both single objects and arrays
    if isinstance(data, list):
        records = data
    else:
        records = [data]
    
    processed_records = []
    for record in records:
        # Validate required fields
        validated = validate_record(record)
        
        # Transform and enrich
        transformed = transform_record(validated)
        
        processed_records.append(transformed)
    
    return json.dumps(processed_records, indent=2), len(processed_records)


def process_csv(content: str) -> tuple:
    """
    Process CSV content: parse, validate, transform to JSON.
    
    Args:
        content: Raw CSV string
    
    Returns:
        tuple: (processed JSON string, record count)
    """
    reader = csv.DictReader(StringIO(content))
    
    processed_records = []
    for row in reader:
        # Validate and transform
        validated = validate_record(dict(row))
        transformed = transform_record(validated)
        processed_records.append(transformed)
    
    return json.dumps(processed_records, indent=2), len(processed_records)


def validate_record(record: dict) -> dict:
    """
    Validate a single record, removing null values and normalizing fields.
    
    Args:
        record: Input record dictionary
    
    Returns:
        dict: Validated record
    """
    # Remove empty/null values
    validated = {k: v for k, v in record.items() if v is not None and v != ''}
    
    # Normalize field names to lowercase
    validated = {k.lower().replace(' ', '_'): v for k, v in validated.items()}
    
    return validated


def transform_record(record: dict) -> dict:
    """
    Transform and enrich a record with metadata.
    
    Args:
        record: Validated record dictionary
    
    Returns:
        dict: Transformed record with added metadata
    """
    # Add processing metadata
    record['_metadata'] = {
        'processed_at': datetime.utcnow().isoformat(),
        'environment': ENVIRONMENT,
        'processor_version': '1.0.0'
    }
    
    return record


def move_to_processed(bucket: str, key: str):
    """
    Move processed file to a 'processed' folder in the source bucket.
    
    Args:
        bucket: S3 bucket name
        key: Original object key
    """
    new_key = key.replace('incoming/', 'completed/')
    
    # Copy to new location
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': key},
        Key=new_key
    )
    
    # Delete original
    s3_client.delete_object(Bucket=bucket, Key=key)
    
    logger.info(f"Moved {key} to {new_key}")
