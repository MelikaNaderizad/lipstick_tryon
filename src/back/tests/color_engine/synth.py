# -*- coding: utf-8 -*-
"""
تولید عکس‌های فرضی (Synthetic) که شبیه‌سازی می‌کنن یه عکس Swatch واقعی زیر
شرایط نوری مختلف چطور به نظر می‌رسه — برای تست پایپ‌لاین بدون عکس واقعی.

هر عکس شامل ۳ کادر کنار همه: پوست خالی | سواچ رژ | (اختیاری) کارت خاکستری
"""
import numpy as np
from PIL import Image

from app.color_engine.colorspace import (
    rgb255_to_linear,
    linear_to_rgb255,
    hex_to_rgb255,
)

PATCH_W, PATCH_H = 200, 200
GAP = 20


def _solid_patch_linear(hex_color, noise_std=0.01):
    linear = rgb255_to_linear(hex_to_rgb255(hex_color))
    patch = np.tile(linear, (PATCH_H, PATCH_W, 1))
    noise = np.random.normal(0, noise_std, patch.shape)
    return np.clip(patch + noise, 0, 1)


def make_synthetic_swatch_image(
    skin_hex,
    pigment_hex,
    illuminant_gain,  # (r,g,b) ضریب کج‌شدگی نور که روی کل تصویر اعمال می‌شه
    include_gray_card=True,
    swatch_skin_bleed=0.05,  # مقدار کمی نشتِ رنگ پوست از زیر رژِ نه‌کاملاً‌کدر
):
    """
    خروجی: (image_rgb255, boxes) که boxes مختصات هر کادره.
    """
    skin_linear = _solid_patch_linear(skin_hex)
    pigment_linear = _solid_patch_linear(pigment_hex)
    # سواچ واقعی معمولاً کمی از پوست زیرش نشت می‌کنه (نه ۱۰۰٪ کدر)
    skin_ref_linear = rgb255_to_linear(hex_to_rgb255(skin_hex))
    swatch_linear = (1 - swatch_skin_bleed) * pigment_linear + swatch_skin_bleed * skin_ref_linear

    patches = [skin_linear, swatch_linear]
    if include_gray_card:
        gray_linear = _solid_patch_linear("#B0B0B0")
        patches.append(gray_linear)

    n = len(patches)
    total_w = n * PATCH_W + (n + 1) * GAP
    total_h = PATCH_H + 2 * GAP
    canvas_linear = np.full((total_h, total_w, 3), 0.9)  # پس‌زمینه‌ی روشن خنثی

    boxes = []
    x = GAP
    for patch in patches:
        canvas_linear[GAP:GAP + PATCH_H, x:x + PATCH_W, :] = patch
        boxes.append((x, GAP, x + PATCH_W, GAP + PATCH_H))
        x += PATCH_W + GAP

    # اعمال کج‌شدگی نور (illuminant) روی کل تصویر
    gain = np.asarray(illuminant_gain, dtype=np.float64)
    lit_linear = np.clip(canvas_linear * gain, 0, 1)

    image_rgb255 = linear_to_rgb255(lit_linear)

    result_boxes = {"skin_box": boxes[0], "swatch_box": boxes[1]}
    if include_gray_card:
        result_boxes["gray_box"] = boxes[2]
    return image_rgb255, result_boxes


def save_image(rgb255, path):
    Image.fromarray(rgb255).save(path)
