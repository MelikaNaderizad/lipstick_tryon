# -*- coding: utf-8 -*-
"""
تولید عکس Swatch جای‌گذار (Placeholder) — چون هنوز عکس واقعی از هیچ Seller
واقعی نداریم. یه لکه‌ی رنگی با کمی گرادیان و نویز می‌سازه (نه یه مربع تخت
تک‌رنگ) تا واقع‌بینانه‌تر به نظر برسه و بشه با color_engine.extraction هم
تستش کرد. فقط برای Demo/Seed استفاده می‌شه، نه Production واقعی.
"""
import io

import numpy as np
from PIL import Image


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def generate_placeholder_swatch_png(hex_color: str, width: int = 300, height: int = 200) -> bytes:
    rng = np.random.default_rng(abs(hash(hex_color)) % (2**32))
    base = np.array(_hex_to_rgb(hex_color), dtype=np.float64)

    # کمی گرادیان روشنایی از چپ به راست + نویز ریز، تا سطح صاف/غیرواقعی نباشه
    gradient = np.linspace(-12, 12, width)
    noise = rng.normal(0, 4, size=(height, width))

    img = np.zeros((height, width, 3), dtype=np.float64)
    for c in range(3):
        channel = base[c] + gradient[np.newaxis, :] + noise
        img[:, :, c] = np.clip(channel, 0, 255)

    img_uint8 = img.astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(img_uint8, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()
