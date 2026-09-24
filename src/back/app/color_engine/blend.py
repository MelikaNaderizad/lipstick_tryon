# -*- coding: utf-8 -*-
"""
محاسبه‌ی render_color برای هر (shade, skin_tone_anchor) — برای پیش‌نمایش استاتیک.
بلندینگ در فضای خطی (linear RGB) انجام می‌شه.
"""
import numpy as np

from app.color_engine.colorspace import (
    rgb255_to_linear,
    linear_to_rgb255,
    rgb255_to_hex,
    hex_to_rgb255,
)

# ضریب پوشش ثابت برای همه‌ی انواع محصول (طبق SPECULAR_HIGHLIGHT_SPEC.md)؛ باید با BASE_OPACITY توی src/live-demo/index.html یکی بمونه.
BASE_OPACITY = 0.85


def render_color_for_anchor(base_pigment_hex, anchor_reference_hex):
    pigment_linear = rgb255_to_linear(hex_to_rgb255(base_pigment_hex))
    anchor_linear = rgb255_to_linear(hex_to_rgb255(anchor_reference_hex))
    blended = BASE_OPACITY * pigment_linear + (1 - BASE_OPACITY) * anchor_linear
    return rgb255_to_hex(linear_to_rgb255(blended))


def compute_all_render_profiles(base_pigment_hex, anchors):
    return [
        {
            "skin_tone_anchor_id": a["id"],
            "render_color": render_color_for_anchor(base_pigment_hex, a["reference_color"]),
        }
        for a in anchors
    ]