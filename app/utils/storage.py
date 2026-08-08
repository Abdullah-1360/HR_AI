"""
app/utils/storage.py
Boto3 S3-compatible object storage client for resume PDFs and other files.
"""
import io
import logging
from functools import lru_cache
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_s3_client():
    settings = get_settings()
    endpoint = settings.minio_endpoint
    if not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}/storage/v1/s3" if settings.minio_secure else f"http://{endpoint}"
    
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="ap-southeast-1"
    )


def ensure_bucket(bucket_name: str) -> None:
    """Create a bucket if it does not already exist."""
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == '404' or error_code == 'NoSuchBucket':
            try:
                client.create_bucket(Bucket=bucket_name)
                logger.info("storage.create_bucket bucket=%s", bucket_name)
            except ClientError as exc:
                logger.error("storage.bucket_create_failed bucket=%s error=%s", bucket_name, exc)
                raise
        else:
            logger.error("storage.bucket_check_failed bucket=%s error=%s", bucket_name, e)
            raise


def upload_bytes(
    bucket_name: str,
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload raw bytes to S3. Returns the object_name (S3 key).
    Ensures the bucket exists before uploading.
    """
    client = _get_s3_client()
    ensure_bucket(bucket_name)

    try:
        client.put_object(
            Bucket=bucket_name,
            Key=object_name,
            Body=data,
            ContentType=content_type,
        )
        logger.info("storage.uploaded bucket=%s key=%s size=%d", bucket_name, object_name, len(data))
        return object_name
    except ClientError as exc:
        logger.error("storage.upload_failed key=%s error=%s", object_name, exc)
        raise


def download_bytes(bucket_name: str, object_name: str) -> bytes:
    """Download an object from S3 and return its bytes."""
    client = _get_s3_client()
    try:
        response = client.get_object(Bucket=bucket_name, Key=object_name)
        data = response['Body'].read()
        return data
    except ClientError as exc:
        logger.error("storage.download_failed key=%s error=%s", object_name, exc)
        raise


def get_presigned_url(
    bucket_name: str,
    object_name: str,
    expires_hours: int = 1,
) -> Optional[str]:
    """Generate a pre-signed URL for temporary access to an object."""
    client = _get_s3_client()
    try:
        url = client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expires_hours * 3600
        )
        return url
    except ClientError as exc:
        logger.warning("storage.presign_failed key=%s error=%s", object_name, exc)
        return None
