# -*- coding: utf-8 -*-
"""
پایپ‌لاین استخراج رنگ خالص رژ (base_pigment_color) از عکس Swatch با دو کادر
دستی (پوست خالی + رژ).

روش جداسازی پیگمنت از پوست داخل کادر رژ: GrabCut (الگوریتم کلاسیک segmentation
بر پایه‌ی Graph Cut — Rother/Kolmogorov/Blake 2004، پیاده‌سازی OpenCV). دقیقاً
همون مسئله‌ای که GrabCut براش طراحی شده: «کاربر یه کادر تقریبی دور شیء می‌کشه،
الگوریتم مرز دقیق رو خودش پیدا می‌کنه». این نسخه‌ی صنعتی‌شده‌ی چیزیه که قبلاً
با یه آستانه‌ی ساده‌ی Otsu روی کروما پیاده‌سازی شده بود؛ GrabCut هم رنگ پس‌زمینه
و پیش‌زمینه رو با یه مدل آماری (GMM) یاد می‌گیره و هم همبستگی مکانی پیکسل‌ها رو
در نظر می‌گیره، پس به لکه‌های نامنظم و نویز پوست مقاوم‌تره. کادر پوست هم مستقیم
به‌عنوان «پس‌زمینه‌ی قطعی» به GrabCut داده می‌شه — سرنخ اضافه‌ای که آستانه‌ی
ساده نمی‌تونست ازش استفاده کنه.

اگه GrabCut توی کادر رژ چیزی به‌عنوان پیش‌زمینه پیدا نکنه (مثلاً کادر اشتباهاً
روی پوست خالی کشیده شده)، به میانه‌ی کل کادر برمی‌گرده و هشدار می‌ده.
"""
import cv2
import numpy as np
from PIL import Image

from app.color_engine.colorspace import (
    rgb255_to_linear, linear_to_rgb255, rgb255_to_lab, hex_to_rgb255, rgb255_to_hex,
)

_LAST_RESORT_SKIN_HEX = "#C68642"
_LAST_RESORT_SKIN_LINEAR = rgb255_to_linear(hex_to_rgb255(_LAST_RESORT_SKIN_HEX))

_GRABCUT_ITERATIONS = 5
_MIN_FOREGROUND_PIXELS = 20


def _weighted_target_from_anchors(skin_lab_L, anchor_hex_list, tier_tolerance=6.0):
    scored = [
        (abs(rgb255_to_lab(hex_to_rgb255(h).astype(np.float64))[0] - skin_lab_L), h)
        for h in anchor_hex_list
    ]
    scored.sort(key=lambda t: t[0])
    nearest_diff = scored[0][0]
    same_tier = [h for diff, h in scored if diff <= nearest_diff + tier_tolerance]
    target_linear = np.mean([rgb255_to_linear(hex_to_rgb255(h)) for h in same_tier], axis=0)
    source = "skin_tone_anchor_tier_avg:" + "+".join(same_tier)
    return target_linear, source


def load_image(path):
    return np.array(Image.open(path).convert("RGB"))


def crop(image, box):
    x0, y0, x1, y1 = box
    return image[y0:y1, x0:x1, :]


def _robust_linear_mean(patch_rgb255):
    linear = rgb255_to_linear(patch_rgb255).reshape(-1, 3)
    return np.median(linear, axis=0)


def estimate_illuminant_gain(skin_patch_rgb255, gray_patch_rgb255=None, skin_tone_anchors=None,
                             target_anchor_hex=None, mode="exposure"):
    if gray_patch_rgb255 is not None:
        gray_linear = _robust_linear_mean(gray_patch_rgb255)
        target = np.mean(gray_linear)
        gain = np.clip(target / np.clip(gray_linear, 1e-6, None), 0.4, 2.5)
        source = "gray_card"
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
        y_w = np.array([0.2126729, 0.7151522, 0.0721750])
        scale = float(target_linear @ y_w) / max(float(skin_linear @ y_w), 1e-6)
        gain = np.full(3, np.clip(scale, 0.4, 2.5))
        return gain, source + "|exposure_only"

    gain = target_linear / np.clip(skin_linear, 1e-6, None)
    gain = np.clip(gain, 0.4, 2.5)
    return gain, source + "|full"


def _drop_highlights(pixels_rgb255, margin_L=12.0):
    """pixels_rgb255: آرایه‌ی Nx3. پیکسل‌های خیلی روشن‌تر از میانه (برق گلاس) رو کنار می‌ذاره."""
    L = rgb255_to_lab(pixels_rgb255)[:, 0]
    keep = L <= np.median(L) + margin_L
    if keep.sum() < 20:
        return pixels_rgb255, 0
    return pixels_rgb255[keep], int((~keep).sum())


def _grabcut_foreground_pixels(image_rgb255, swatch_box, skin_box, iterations=_GRABCUT_ITERATIONS):
    """
    جداسازی پیگمنت رژ از پوست داخل کادر رژ، با GrabCut. کادر پوست به‌عنوان
    پس‌زمینه‌ی قطعی (GC_BGD) به الگوریتم داده می‌شه.
    خروجی: (پیکسل‌های Nx3 پیش‌زمینه‌ی داخل کادر رژ، درصد کادر که پس‌زمینه تشخیص
    داده شد) یا (None, None) اگه GrabCut چیزی پیدا نکرد.
    """
    h, w = image_rgb255.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
    x0, y0, x1, y1 = swatch_box
    mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
    sx0, sy0, sx1, sy1 = skin_box
    mask[sy0:sy1, sx0:sx1] = cv2.GC_BGD

    image_bgr = cv2.cvtColor(image_rgb255, cv2.COLOR_RGB2BGR)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(image_bgr, mask, None, bgd_model, fgd_model, iterations, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None, None

    box_mask = np.zeros((h, w), dtype=bool)
    box_mask[y0:y1, x0:x1] = True
    fg_mask = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)) & box_mask
    if int(fg_mask.sum()) < _MIN_FOREGROUND_PIXELS:
        return None, None

    excluded_fraction = 1.0 - fg_mask.sum() / box_mask.sum()
    return image_rgb255[fg_mask], float(excluded_fraction)


def extract_base_pigment_color(image_rgb255, skin_box, swatch_box, gray_box=None, skin_tone_anchors=None,
                               target_anchor_hex=None, correction_mode="exposure", swatch_coverage=1.0,
                               exclude_highlights=True):
    skin_patch = crop(image_rgb255, skin_box)
    full_swatch_patch = crop(image_rgb255, swatch_box)
    gray_patch = crop(image_rgb255, gray_box) if gray_box else None
    warnings = []

    if skin_patch.size == 0 or full_swatch_patch.size == 0:
        raise ValueError("کادر پوست یا سواچ خالیه (مختصات خارج از تصویر)")

    fg_pixels, excluded_fraction = _grabcut_foreground_pixels(image_rgb255, swatch_box, skin_box)
    if fg_pixels is None:
        # GrabCut چیزی پیدا نکرد (مثلاً کادر رژ اشتباهاً روی پوست خالی کشیده شده)
        # — به کل کادر برمی‌گردیم تا حداقل خطا ندیم، ولی هشدار می‌دیم.
        fg_pixels = full_swatch_patch.reshape(-1, 3)
        excluded_fraction = 0.0
        warnings.append("swatch_pigment_not_found")

    n_dropped = 0
    if exclude_highlights:
        fg_pixels, n_dropped = _drop_highlights(fg_pixels)

    gain, correction_source = estimate_illuminant_gain(
        skin_patch, gray_patch, skin_tone_anchors,
        target_anchor_hex=target_anchor_hex, mode=correction_mode,
    )

    swatch_linear = _robust_linear_mean(fg_pixels)
    skin_linear = _robust_linear_mean(skin_patch)
    swatch_corr = swatch_linear * gain
    skin_corr = skin_linear * gain

    if swatch_coverage < 1.0:
        c = max(float(swatch_coverage), 0.3)
        swatch_corr = (swatch_corr - (1 - c) * skin_corr) / c

    corrected_linear = np.clip(swatch_corr, 0.0, 1.0)
    corrected_rgb255 = linear_to_rgb255(corrected_linear)
    corrected_lab = rgb255_to_lab(corrected_rgb255.astype(np.float64))

    if np.any(np.isclose(gain, 0.4)) or np.any(np.isclose(gain, 2.5)):
        warnings.append("lighting_correction_clamped")
    sw_lab = rgb255_to_lab(fg_pixels.astype(np.float64))
    if float(np.std(sw_lab[:, 0])) > 12.0:
        warnings.append("swatch_not_uniform")
    if len(fg_pixels) < 400:
        warnings.append("swatch_patch_small")
    if float(np.max(corrected_linear)) >= 0.999:
        warnings.append("swatch_overexposed")
    if float(np.max(swatch_linear)) < 0.01:
        warnings.append("swatch_too_dark")
    if excluded_fraction > 0.4:
        # کادر رژ روی پیگمنت دقیق نبود؛ بیش از نصف کادر پوست تشخیص داده شد و کنار
        # گذاشته شد. رنگ نهایی همچنان از خودِ پیگمنته، ولی کادر دقیق‌تر بهتره.
        warnings.append("swatch_box_loosely_cropped")

    return {
        "base_pigment_color": rgb255_to_hex(corrected_rgb255),
        "base_pigment_lab": corrected_lab.tolist(),
        "illuminant_gain": np.asarray(gain).tolist(),
        "correction_source": correction_source,
        "raw_swatch_color": rgb255_to_hex(linear_to_rgb255(swatch_linear)),
        "highlight_pixels_dropped": n_dropped,
        "vivid_pixels_excluded_fraction": round(excluded_fraction, 3),
        "warnings": warnings,
    }
