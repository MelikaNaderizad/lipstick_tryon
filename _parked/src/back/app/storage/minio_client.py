# -*- coding: utf-8 -*-
"""
Client ساده برای MinIO (سازگار با S3) — برای آپلود عکس محصول/Swatch و
گرفتن URL قابل‌نمایش. PostgreSQL فقط مسیر (object_name) رو نگه می‌داره،
نه خودِ فایل رو — دقیقاً طبق چیزی که در معماری اولیه تصمیم گرفته شد.
"""
import os
from datetime import timedelta
from io import BytesIO

from minio import Minio
from minio.error import S3Error

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "virtual-tryon")

_client = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
    return _client


def ensure_bucket(bucket_name: str = MINIO_BUCKET) -> None:
    client = get_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def upload_bytes(
    data: bytes,
    object_name: str,
    content_type: str = "application/octet-stream",
    bucket_name: str = MINIO_BUCKET,
) -> str:
    """آپلود مستقیم از بایت (مثلاً محتوای فایل آپلودشده در FastAPI). خروجی: object_name."""
    client = get_client()
    ensure_bucket(bucket_name)
    client.put_object(
        bucket_name,
        object_name,
        data=BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def upload_file(local_path: str, object_name: str, bucket_name: str = MINIO_BUCKET) -> str:
    """آپلود از یه فایل روی دیسک (مثلاً برای Seed کردن نمونه‌ها)."""
    client = get_client()
    ensure_bucket(bucket_name)
    client.fput_object(bucket_name, object_name, local_path)
    return object_name


def object_exists(object_name: str, bucket_name: str = MINIO_BUCKET) -> bool:
    client = get_client()
    try:
        client.stat_object(bucket_name, object_name)
        return True
    except S3Error:
        return False


def get_presigned_url(
    object_name: str, bucket_name: str = MINIO_BUCKET, expires_minutes: int = 60
) -> str:
    """
    URL موقت و قابل‌نمایش برای یه عکس. چون bucket خصوصیه (نه Public)،
    Frontend همیشه از همین تابع باید URL نمایش رو بگیره، نه مسیر خام دیتابیس.
    """
    client = get_client()
    return client.presigned_get_object(
        bucket_name, object_name, expires=timedelta(minutes=expires_minutes)
    )
