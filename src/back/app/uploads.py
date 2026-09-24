# -*- coding: utf-8 -*-
"""
خوندن و اعتبارسنجی عکس آپلودی — یک‌جا برای همه‌ی مسیرها (/extract، /apply، /seller/...).
هر آپلودی از این تابع رد می‌شه، پس تبدیل ICC → sRGB، سقف حجم و سقف پیکسل همه‌جا یکسانه.
"""
import re

from fastapi import HTTPException, UploadFile, status

from app.imaging import ImageError, decode_image

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def read_upload(upload: UploadFile):
    """-> (بایت‌های خام, آرایه‌ی HxWx3 uint8 در sRGB, متادیتا, پسوند فایل). فقط توی endpoint های sync (def) صدا بزن."""
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "فقط JPEG/PNG/WebP قبول می‌شه")
    raw = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "حجم فایل بیشتر از ۱۰ مگابایته")
    try:
        image, meta = decode_image(raw)
    except ImageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return raw, image, meta, ALLOWED_TYPES[upload.content_type]
