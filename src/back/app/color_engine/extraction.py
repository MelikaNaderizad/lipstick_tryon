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


def estimate_illuminant_gain(
    skin_patch_rgb255,
    gray_patch_rgb255=None,
    skin_tone_anchors=None,
    target_anchor_hex=None,
    mode="exposure",
):
    """
    ضریب تصحیح نور (per-channel gain) رو برمی‌گردونه که وقتی روی تصویر ضرب بشه،
    رنگ رو به حالت "زیر نور خنثی" نزدیک می‌کنه.

    اولویت منابع تصحیح:
    ۱. کارت خاکستری (اگه seller گذاشته باشه) — دقیق‌ترین حالت.
    ۲. لیست skin_tone_anchor موجود در دیتابیس — نزدیک‌ترین Anchor (بر اساس
       روشنایی پوست seller) به‌عنوان "چیزی که پوست باید زیر نور خنثی باشه" در نظر گرفته می‌شه.
    ۳. یه ثابت آخرین راه‌حل، فقط برای جلوگیری از خطا (نباید در عمل بهش برسیم).

    target_anchor_hex: اگه seller خودش تناژ پوستش رو انتخاب کرده باشه، همون رنگ
    مستقیم هدف تصحیح می‌شه (به‌جای حدس زدن از روی روشنایی عکس).

    mode (فقط برای مسیرهای مبتنی بر پوست، نه کارت خاکستری):
      "exposure" (پیش‌فرض): فقط یه ضریب روشنایی یکسان برای هر سه کانال — رنگ‌مایه
                  (hue) دست‌نخورده می‌مونه. چون Anchorها فقط ۶ تا و درشتن، تصحیح
                  رنگی کامل روی عکس واقعی می‌تونه رنگ رژ رو به سمت زرد/نارنجی ببره.
      "full"    : ضریب جدا برای هر کانال (تصحیح رنگی کامل).
      "none"    : بدون تصحیح.
    """
    if gray_patch_rgb255 is not None:
        gray_linear = _robust_linear_mean(gray_patch_rgb255)
        target = np.mean(gray_linear)  # می‌خوایم هر سه کانال برابر بشن
        gain = np.clip(target / np.clip(gray_linear, 1e-6, None), 0.4, 2.5)
        source = "gray_card"
        # کارت خاکستری فقط «کجی رنگ» (white balance) رو درست می‌کنه، نه روشنایی
        # (بازتاب واقعی کارت رو نمی‌دونیم). اگه seller تناژ پوستش رو انتخاب کرده،
        # روشنایی رو هم با همون تصحیح می‌کنیم؛ وگرنه فقط رنگ.
        if target_anchor_hex and mode != "none":
            skin_wb = _robust_linear_mean(skin_patch_rgb255) * gain
            y_w = np.array([0.2126729, 0.7151522, 0.0721750])
            t_lin = rgb255_to_linear(hex_to_rgb255(target_anchor_hex))
            scale = float(t_lin @ y_w) / max(float(skin_wb @ y_w), 1e-6)
            gain = gain * np.clip(scale, 0.4, 2.5)
            source = "gray_card+selected_anchor_exposure"
        return gain, source

    skin_linear = _robust_linear_mean(skin_patch_rgb255)

    if mode == "none":
        return np.ones(3), "none"

    if target_anchor_hex:
        target_linear = rgb255_to_linear(hex_to_rgb255(target_anchor_hex))
        source = "selected_anchor:" + target_anchor_hex
    elif skin_tone_anchors:
        skin_lab_L = rgb255_to_lab(linear_to_rgb255(skin_linear).astype(np.float64))[0]
        target_linear, source = _weighted_target_from_anchors(skin_lab_L, skin_tone_anchors)
    else:
        target_linear = _LAST_RESORT_SKIN_LINEAR
        source = "last_resort_constant"

    if mode == "exposure":
        # فقط روشنایی: نسبت luminance (Y) هدف به پوست، برای هر سه کانال یکسان
        y_w = np.array([0.2126729, 0.7151522, 0.0721750])
        scale = float(target_linear @ y_w) / max(float(skin_linear @ y_w), 1e-6)
        gain = np.full(3, np.clip(scale, 0.4, 2.5))
        return gain, source + "|exposure_only"

    gain = target_linear / np.clip(skin_linear, 1e-6, None)
    gain = np.clip(gain, 0.4, 2.5)
    return gain, source + "|full"


def _drop_highlights(patch_rgb255, margin_L=12.0):
    """پیکسل‌های خیلی روشن‌تر از میانه‌ی L (هایلایت/برق گلاس) رو کنار می‌ذاره."""
    flat = patch_rgb255.reshape(-1, 3).astype(np.float64)
    L = rgb255_to_lab(flat)[:, 0]
    keep = L <= np.median(L) + margin_L
    if keep.sum() < 20:  # چیزی نمونده؛ همه رو نگه دار
        return patch_rgb255, 0
    return flat[keep].reshape(-1, 1, 3), int((~keep).sum())


def extract_base_pigment_color(
    image_rgb255,
    skin_box,
    swatch_box,
    gray_box=None,
    skin_tone_anchors=None,
    target_anchor_hex=None,
    correction_mode="exposure",
    swatch_coverage=1.0,
    exclude_highlights=True,
):
    """
    ورودی: تصویر کامل + مختصات کادرها (پیکسل) + لیست reference_color های Anchor
    swatch_coverage: پوشش سواچ روی پوست (۱ = کاملاً کدر). راهنمای عکس‌گیری دو لایه‌ی
        کامل می‌خواد، پس پیش‌فرض ۱ (بدون کم کردن سهم پوست). اگه <۱ باشه:
        pigment = (swatch - (1-c)*skin) / c  در فضای خطی.
    خروجی: dict شامل رنگ نهایی (hex)، متادیتای تشخیصی، و لیست warnings
    """
    skin_patch = crop(image_rgb255, skin_box)
    swatch_patch = crop(image_rgb255, swatch_box)
    gray_patch = crop(image_rgb255, gray_box) if gray_box else None
    warnings = []

    if skin_patch.size == 0 or swatch_patch.size == 0:
        raise ValueError("کادر پوست یا سواچ خالیه (مختصات خارج از تصویر)")

    n_dropped = 0
    if exclude_highlights:
        swatch_patch, n_dropped = _drop_highlights(swatch_patch)

    gain, correction_source = estimate_illuminant_gain(
        skin_patch, gray_patch, skin_tone_anchors,
        target_anchor_hex=target_anchor_hex, mode=correction_mode,
    )

    swatch_linear = _robust_linear_mean(swatch_patch)
    skin_linear = _robust_linear_mean(skin_patch)
    swatch_corr = swatch_linear * gain
    skin_corr = skin_linear * gain

    if swatch_coverage < 1.0:
        c = max(float(swatch_coverage), 0.3)
        swatch_corr = (swatch_corr - (1 - c) * skin_corr) / c

    corrected_linear = np.clip(swatch_corr, 0.0, 1.0)
    corrected_rgb255 = linear_to_rgb255(corrected_linear)
    corrected_lab = rgb255_to_lab(corrected_rgb255.astype(np.float64))

    # --- هشدارهای کیفیت (برای نمایش به seller) ---
    if np.any(np.isclose(gain, 0.4)) or np.any(np.isclose(gain, 2.5)):
        warnings.append("lighting_correction_clamped")
    sw_lab = rgb255_to_lab(swatch_patch.reshape(-1, 3).astype(np.float64))
    if float(np.std(sw_lab[:, 0])) > 12.0:
        warnings.append("swatch_not_uniform")
    if swatch_patch.shape[0] * swatch_patch.shape[1] < 400:
        warnings.append("swatch_patch_small")
    if float(np.max(corrected_linear)) >= 0.999:
        warnings.append("swatch_overexposed")
    if float(np.max(swatch_linear)) < 0.01:
        warnings.append("swatch_too_dark")

    return {
        "base_pigment_color": rgb255_to_hex(corrected_rgb255),
        "base_pigment_lab": corrected_lab.tolist(),
        "illuminant_gain": np.asarray(gain).tolist(),
        "correction_source": correction_source,
        "raw_swatch_color": rgb255_to_hex(linear_to_rgb255(swatch_linear)),
        "highlight_pixels_dropped": n_dropped,
        "warnings": warnings,
    }
