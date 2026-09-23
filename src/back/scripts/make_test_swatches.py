# -*- coding: utf-8 -*-
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.color_engine.colorspace import hex_to_rgb255, linear_to_rgb255, rgb255_to_linear  # noqa: E402
from app.color_engine.swatch_template import DEFAULT_SKIN_BOX, DEFAULT_SWATCH_BOX  # noqa: E402

GRAY_BOX = (0.02, 0.02, 0.14, 0.14)

LIGHTS = {
    "neutral": (1.00, 1.00, 1.00),
    "warm": (1.15, 1.00, 0.80),
    "cool": (0.90, 1.00, 1.15),
    "dim": (0.60, 0.60, 0.60),
    "bright": (1.30, 1.30, 1.30),
}


def make_swatch_image(skin_hex, pigment_hex, light="neutral", gloss_highlight=False,
                      gray_card=False, w=800, h=600, noise=2.0, seed=0):
    rng = np.random.default_rng(seed)
    light_v = np.array(LIGHTS[light] if isinstance(light, str) else light, dtype=np.float64)
    skin = rgb255_to_linear(hex_to_rgb255(skin_hex)) * light_v
    pig = rgb255_to_linear(hex_to_rgb255(pigment_hex)) * light_v

    img = np.zeros((h, w, 3))
    img[:, : w // 2] = skin
    img[:, w // 2:] = pig

    ramp = np.linspace(0.96, 1.04, w)[None, :, None]
    img = img * ramp

    if gloss_highlight:
        x0, y0, x1, y1 = DEFAULT_SWATCH_BOX
        cx, cy = int((x0 + x1) / 2 * w), int((y0 + y1) / 2 * h)
        yy, xx = np.mgrid[0:h, 0:w]
        blob = np.exp(-(((xx - cx) / (0.05 * w)) ** 2 + ((yy - cy) / (0.05 * h)) ** 2))[..., None]
        img = img * (1 - 0.85 * blob) + 0.95 * light_v * 0.85 * blob

    if gray_card:
        gx0, gy0, gx1, gy1 = GRAY_BOX
        img[int(gy0 * h):int(gy1 * h), int(gx0 * w):int(gx1 * w)] = 0.5 * light_v

    rgb = linear_to_rgb255(np.clip(img, 0, 1)).astype(np.float64)
    rgb += rng.normal(0, noise, rgb.shape)
    return np.clip(rgb, 0, 255).astype(np.uint8)


CASES = [
    ("rose-classic-neutral", "#B0223A", "liquid", "#F4DBC9", "neutral", False, False, None),
    ("coral-warm-light", "#E0645A", "liquid", "#D9B48A", "warm", False, False, None,
     "نور رنگی بدون کارت خاکستری: حالت پیش‌فرض exposure کجی رنگ رو تصحیح نمی‌کنه"),
    ("warm-nude-cool-light", "#B97A62", "stick", "#F4DBC9", "cool", False, False, None),
    ("burgundy-dark-skin", "#7A2E3B", "stick", "#9C7A52", "neutral", False, False, None),
    ("gloss-with-highlight", "#DC5B6B", "gloss", "#D9B48A", "neutral", True, False, None),
    ("dim-auto-anchor", "#B0223A", "liquid", "#F4DBC9", "dim", False, False, None,
     "نور کم بدون انتخاب Anchor: سیستم پوست روشن کم‌نور رو با پوست تیره اشتباه می‌گیره"),
    ("dim-selected-anchor", "#B0223A", "liquid", "#F4DBC9", "dim", False, False, "#F4DBC9"),
    ("dim-warm-graycard-selected", "#E0645A", "balm", "#D9B48A", "dim", False, True, "#D9B48A"),
]


def main(out_dir="test_swatches"):
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for i, case in enumerate(CASES):
        name, pig, cat, skin, light, gloss, gray, sel = case[:8]
        note = case[8] if len(case) > 8 else None
        img = make_swatch_image(skin, pig, light, gloss, gray, seed=i)
        fname = f"{name}.jpg"
        Image.fromarray(img).save(os.path.join(out_dir, fname), quality=95)
        manifest.append({
            "file": fname, "name": name, "category": cat,
            "expected_color": pig, "skin": skin, "light": light,
            "gloss_highlight": gloss,
            "gray_box": ",".join(str(v) for v in GRAY_BOX) if gray else None,
            "selected_anchor_hex": sel,
            "known_limit": note,
        })
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"{len(manifest)} عکس + manifest.json توی «{out_dir}» ساخته شد.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test_swatches")
