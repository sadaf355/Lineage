"""Phase 5 storage abstraction. Local encrypted files remain the default; S3-compatible object storage is opt-in."""
from __future__ import annotations
import os
from pathlib import Path
from urllib.parse import urlparse
from app.core.config import get_settings
settings = get_settings()

def _s3():
    import boto3
    return boto3.client("s3", region_name=settings.S3_REGION or None,
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None)

def enabled() -> bool:
    return settings.STORAGE_BACKEND.lower() == "s3"

def put_file(local_path: str, key: str) -> str:
    if not enabled(): return local_path
    if not settings.S3_BUCKET: raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
    key = f"{settings.S3_PREFIX.strip('/')}/{key.lstrip('/')}" if settings.S3_PREFIX else key.lstrip('/')
    _s3().upload_file(local_path, settings.S3_BUCKET, key, ExtraArgs={"ServerSideEncryption":"AES256"})
    Path(local_path).unlink(missing_ok=True)
    return f"s3://{settings.S3_BUCKET}/{key}"

def download_to_file(storage_path: str, local_path: str) -> None:
    if not storage_path.startswith("s3://"):
        Path(local_path).write_bytes(Path(storage_path).read_bytes()); return
    parsed=urlparse(storage_path)
    _s3().download_file(parsed.netloc, parsed.path.lstrip('/'), local_path)

def delete(storage_path: str) -> None:
    if storage_path.startswith("s3://"):
        parsed=urlparse(storage_path); _s3().delete_object(Bucket=parsed.netloc, Key=parsed.path.lstrip('/')); return
    Path(storage_path).unlink(missing_ok=True)
