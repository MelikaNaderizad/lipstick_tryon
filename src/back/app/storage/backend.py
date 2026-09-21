# -*- coding: utf-8 -*-
"""
لایه‌ی ذخیره‌ی فایل با دو حالت (انتخاب با متغیر محیطی STORAGE_BACKEND):

  minio (پیش‌فرض) : MinIO / S3 — برای تحویل نهایی و Docker
  local           : ذخیره روی دیسک (پوشه‌ی LOCAL_STORAGE_DIR، پیش‌فرض ./local_storage)
                    — برای دمو/تست سریع بدون نیاز به Docker و MinIO

بقیه‌ی برنامه فقط از همین ماژول استفاده می‌کنه، نه مستقیم از minio_client.
"""
import os
from pathlib import Path


def backend() -> str:
    return os.getenv("STORAGE_BACKEND", "minio").lower()


def local_dir() -> Path:
    return Path(os.getenv("LOCAL_STORAGE_DIR", "local_storage")).resolve()


def _local_path(object_name: str) -> Path:
    base = local_dir()
    path = (base / object_name).resolve()
    if base != path and base not in path.parents:
        raise ValueError("مسیر فایل نامعتبره")
    return path


def upload_bytes(data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    if backend() == "local":
        path = _local_path(object_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return object_name
    from app.storage import minio_client
    return minio_client.upload_bytes(data, object_name, content_type=content_type)


def upload_file(local_path: str, object_name: str) -> str:
    with open(local_path, "rb") as fh:
        return upload_bytes(fh.read(), object_name)


def object_exists(object_name: str) -> bool:
    if backend() == "local":
        return _local_path(object_name).is_file()
    from app.storage import minio_client
    return minio_client.object_exists(object_name)


def get_url(object_name: str):
    """آدرس قابل‌نمایش برای مرورگر، یا None اگه فایل نیست / ذخیره‌گاه در دسترس نیست."""
    if not object_name:
        return None
    try:
        if not object_exists(object_name):
            return None
        if backend() == "local":
            return f"/files/{object_name}"
        from app.storage import minio_client
        return minio_client.get_presigned_url(object_name)
    except Exception:
        return None
