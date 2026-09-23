# -*- coding: utf-8 -*-
"""
خوندن عکس آپلودی و تبدیلش به آرایه‌ی sRGB (uint8) برای موتور رنگ.

نسبت به نسخه‌ی قبلی (داخل router):
  - پروفایل رنگی ICC توی عکس (مثلاً Display P3 آیفون) به sRGB تبدیل می‌شه. قبلاً
    نادیده گرفته می‌شد و همه‌ی رنگ‌ها جابه‌جا می‌شد.
  - سقف تعداد پیکسل و گرفتن DecompressionBombError (قبلاً ۵۰۰ می‌داد).
"""
import io

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from PIL import ImageCms
except ImportError:  # pragma: no cover
    ImageCms = None

MAX_PROCESS_SIDE = 1600
MAX_PIXELS = 50_000_000


class ImageError(ValueError):
    """عکس نامعتبر یا خارج از محدوده."""


def _to_srgb_rgb(img, icc):
    """(تصویر RGB, آیا تبدیل ICC انجام شد)"""
    if icc and ImageCms is not None:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            dst = ImageCms.createProfile("sRGB")
            work = img if img.mode in ("RGB", "CMYK", "L") else img.convert("RGB")
            out = ImageCms.profileToProfile(work, src, dst, outputMode="RGB")
            if out is not None:
                return out, True
        except Exception:
            pass  # پروفایل خراب یا نامتناسب با mode؛ می‌افتیم روی تبدیل ساده
    return img.convert("RGB"), False


def decode_image(raw: bytes):
    """-> (آرایه‌ی HxWx3 uint8 در sRGB, dict متادیتا). ImageError اگه عکس نامعتبر بود."""
    try:
        img = Image.open(io.BytesIO(raw))
        if img.width * img.height > MAX_PIXELS:
            raise ImageError("رزولوشن عکس خیلی بزرگه")
        icc = img.info.get("icc_profile")
        img.load()
        img = ImageOps.exif_transpose(img)  # عکس‌های موبایل اغلب با EXIF چرخیده‌ان
        img, converted = _to_srgb_rgb(img, icc)
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageError("فایل یه تصویر معتبر نیست")
    if max(img.size) > MAX_PROCESS_SIDE:
        img.thumbnail((MAX_PROCESS_SIDE, MAX_PROCESS_SIDE))
    return np.array(img), {"icc_converted": converted}
