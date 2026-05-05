"""MinIO/S3 client — single boto3 client, helpers for presigned URLs and uploads."""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import BinaryIO

import boto3
from botocore.client import Config

from app.core.config import settings

_client = None


def s3() -> boto3.client:
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
    return _client


def ensure_bucket() -> None:
    client = s3()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:  # noqa: BLE001
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_bytes(
    data: bytes | BinaryIO,
    *,
    folder: str,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload bytes; return a public URL pointing to the object."""
    ensure_bucket()
    today = datetime.utcnow().strftime("%Y/%m/%d")
    key = f"{folder.strip('/')}/{today}/{uuid.uuid4().hex}_{filename}"
    body = io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
    s3().upload_fileobj(
        body,
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": content_type, "ACL": "public-read"},
    )
    return f"{settings.s3_public_url}/{settings.s3_bucket}/{key}"


def presigned_get(key: str, expires: int = 3600) -> str:
    return s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )
