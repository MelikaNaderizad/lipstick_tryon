# -*- coding: utf-8 -*-
"""
پایپ‌لاین استخراج رنگ خالص رژ (base_pigment_color) از عکس Swatch.

فرض: عکس طبق «راهنمای عکس‌گیری» گرفته شده، یعنی دو (یا سه) کادر ثابت داره:
  - کادر پوست خالی
  - کادر سواچ رژ (دو لایه، تقریباً کدر)
  - (اختیاری) کادر کارت خاکستری/سفید

نکته‌ی مهم: ثابت CANONICAL_SKIN_LINEAR_RATIO یه مقدار تقریبی/فرضیه‌ست که باید
با عکس‌های واقعی seller ها کالیبره بشه؛ این نسخه یه v0 قابل تست است، نه نسخه‌ی نهایی.
"""
import numpy as np
from PIL import Image

from app.color_engine.colorspace import (
    rgb255_to_linear,
    linear_to_rgb255,
    rgb255_to_lab,
    hex_to_rgb255,
    rgb255_to_hex,
)

# آخرین راه‌حل وقتی نه کارت خاکستری داریم نه لیست skin_tone_anchor —
# فقط برای جلوگیری از کرش کردن پایپ‌لاین؛ در عمل هیچ‌وقت نباید به این برسیم.
_LAST_RESORT_SKIN_HEX = "#C68642"
_LAST_RESORT_SKIN_LINEAR = rgb255_to_linear(hex_to_rgb255(_LAST_RESORT_SKIN_HEX))


def _weighted_target_from_anchors(skin_lab_L, anchor_hex_list, tier_tolerance=6.0):
    """
    حالا که Anchor ها می‌تونن چند زیرتون (خنثی/زیتونی) در یک سطح روشنی داشته باشن،
    دیگه نمی‌شه صرفاً "نزدیک‌ترین Anchor" رو با معیار L انتخاب کرد — چون در یک سطح
    روشنی، دو Anchor با زیرتون متفاوت وجود داره و انتخاب اشتباه بین اون دو می‌تونه
    یه کجی رنگ اشتباه به تصویر اضافه کنه.

    راه‌حل: تشخیص زیرتون واقعی پوست seller از عکسِ هنوز-تصحیح‌نشده قابل‌اعتماد نیست
    (چون a/b دقیقاً همون چیزیه که زیر نور رنگی خراب شده). پس به‌جای حدس زدن زیرتون،
    میانگین همه‌ی Anchorهایی که در همون "سطح روشنی" (تقریباً هم‌L) هستن رو به‌عنوان
    هدف تصحیح در نظر می‌گیریم — این یه تخمین محافظه‌کارانه و بدون‌سوگیری زیرتونه.
    """
    scored = [
        (abs(rgb255_to_lab(hex_to_rgb255(h).astype(np.float64))[0] - skin_lab_L), h)
        for h in anchor_hex_list
    ]
    scored.sort(key=lambda t: t[0])
    nearest_diff = scored[0][0]

    same_tier = [h for diff, h in scored if diff <= nearest_diff + tier_tolerance]

    target_linear = np.mean(
        [rgb255_to_linear(hex_to_rgb255(h)) for h in same_tier], axis=0
    )
    source = "skin_tone_anchor_tier_avg:" + "+".join(same_tier)
    return target_linear, source


def load_image(path):
    return np.array(Image.open(path).convert("RGB"))


def crop(image, box):
    """box = (x0, y0, x1, y1) به پیکسل"""
    x0, y0, x1, y1 = box
    return image[y0:y1, x0:x1, :]


def _robust_linear_mean(patch_rgb255):
    """میانه (نه میانگین) در فضای خطی، برای مقاومت در برابر نویز/های‌لایت."""
    linear = rgb255_to_linear(patch_rgb255).reshape(-1, 3)
    return np.median(linear, axis=0)


def estimate_illuminant_gain(skin_patch_rgb255, gray_patch_rgb255=None, skin_tone_anchors=None):
    """
    ضریب تصحیح نور (per-channel gain) رو برمی‌گردونه که وقتی روی تصویر ضرب بشه،
    رنگ رو به حالت "زیر نور خنثی" نزدیک می‌کنه.

    اولویت منابع تصحیح:
    ۱. کارت خاکستری (اگه seller گذاشته باشه) — دقیق‌ترین حالت.
    ۲. لیست skin_tone_anchor موجود در دیتابیس — نزدیک‌ترین Anchor (بر اساس
       روشنایی پوست seller) به‌عنوان "چیزی که پوست باید زیر نور خنثی باشه" در نظر گرفته می‌شه.
    ۳. یه ثابت آخرین راه‌حل، فقط برای جلوگیری از خطا (نباید در عمل بهش برسیم).
    """
    if gray_patch_rgb255 is not None:
        gray_linear = _robust_linear_mean(gray_patch_rgb255)
        target = np.mean(gray_linear)  # می‌خوایم هر سه کانال برابر بشن
        gain = target / np.clip(gray_linear, 1e-6, None)
        source = "gray_card"
        return np.clip(gain, 0.4, 2.5), source

    skin_linear = _robust_linear_mean(skin_patch_rgb255)

    if skin_tone_anchors:
        skin_lab_L = rgb255_to_lab(linear_to_rgb255(skin_linear).astype(np.float64))[0]
        target_linear, source = _weighted_target_from_anchors(skin_lab_L, skin_tone_anchors)
    else:
        target_linear = _LAST_RESORT_SKIN_LINEAR
        source = "last_resort_constant"

    gain = target_linear / np.clip(skin_linear, 1e-6, None)
    gain = np.clip(gain, 0.4, 2.5)
    return gain, source


def extract_base_pigment_color(
    image_rgb255,
    skin_box,
    swatch_box,
    gray_box=None,
    skin_tone_anchors=None,
):
    """
    ورودی: تصویر کامل + مختصات کادرها (طبق قالب راهنمای عکس‌گیری) +
           لیست reference_color های موجود در جدول skin_tone_anchor
    خروجی: dict شامل رنگ نهایی (hex) و متادیتای تشخیصی
    """
    skin_patch = crop(image_rgb255, skin_box)
    swatch_patch = crop(image_rgb255, swatch_box)
    gray_patch = crop(image_rgb255, gray_box) if gray_box else None

    gain, correction_source = estimate_illuminant_gain(skin_patch, gray_patch, skin_tone_anchors)

    swatch_linear = _robust_linear_mean(swatch_patch)
    corrected_linear = np.clip(swatch_linear * gain, 0.0, 1.0)
    corrected_rgb255 = linear_to_rgb255(corrected_linear)
    corrected_lab = rgb255_to_lab(corrected_rgb255.astype(np.float64))

    return {
        "base_pigment_color": rgb255_to_hex(corrected_rgb255),
        "base_pigment_lab": corrected_lab.tolist(),
        "illuminant_gain": gain.tolist(),
        "correction_source": correction_source,
    }
