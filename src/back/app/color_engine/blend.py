# -*- coding: utf-8 -*-
"""
محاسبه‌ی render_color برای هر (shade, skin_tone_anchor) — دقیقاً همون چیزی که
یک‌بار در لحظه‌ی آپلود محاسبه و در shade_render_profile ذخیره می‌شه.

بلندینگ در فضای خطی (linear RGB) انجام می‌شه، نه در Lab، چون ترکیب نوری/پوششی
واقعی (opacity) به‌صورت فیزیکی توی نور خطی معنا داره، نه در فضای ادراکی.
"""
import numpy as np

from app.color_engine.colorspace import (
    rgb255_to_linear,
    linear_to_rgb255,
    rgb255_to_hex,
    hex_to_rgb255,
)

# ضریب پوشش تقریبی به ازای نوع Finish — این هم یه فرض اولیه‌ست که با تست واقعی
# (نظر بصری seller روی پیش‌نمایش) قابل تنظیم دقیق‌تره.
OPACITY_BY_FINISH = {
    "matte": 0.88,
    "glossy": 0.68,
}


def render_color_for_anchor(base_pigment_hex, anchor_reference_hex, finish):
    opacity = OPACITY_BY_FINISH.get(finish, 0.8)

    pigment_linear = rgb255_to_linear(hex_to_rgb255(base_pigment_hex))
    anchor_linear = rgb255_to_linear(hex_to_rgb255(anchor_reference_hex))

    blended_linear = opacity * pigment_linear + (1 - opacity) * anchor_linear
    blended_rgb255 = linear_to_rgb255(blended_linear)
    return rgb255_to_hex(blended_rgb255)


def compute_all_render_profiles(base_pigment_hex, finish, anchors):
    """
    anchors: لیستی از dict شامل {"id": ..., "reference_color": "#RRGGBB"}
    خروجی: لیستی از dict آماده برای درج در shade_render_profile
    """
    return [
        {
            "skin_tone_anchor_id": anchor["id"],
            "rendered_color": render_color_for_anchor(
                base_pigment_hex, anchor["reference_color"], finish
            ),
        }
        for anchor in anchors
    ]
