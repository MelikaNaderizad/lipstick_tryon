# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from app.color_engine.colorspace import rgb255_to_lab, hex_to_rgb255, delta_e_76
from app.color_engine.extraction import extract_base_pigment_color
from tests.color_engine.synth import make_synthetic_swatch_image, save_image
from app.color_engine.blend import compute_all_render_profiles

np.random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "synthetic_samples")
os.makedirs(OUT_DIR, exist_ok=True)

GROUND_TRUTH_PIGMENT = "#B22245"  # یه رژ قرمز-رزی فرضی

# ست نهایی Anchor ها: ۳ سطح روشنی × ۲ زیرتون (خنثی/زیتونی)
SKIN_TONE_ANCHORS = [
    "#F4DBC9",  # روشن - خنثی
    "#E6DCB0",  # روشن - زیتونی
    "#D9B48A",  # متوسط - خنثی
    "#C2B47E",  # متوسط - زیتونی
    "#9C7A52",  # گندمی‌تیره - خنثی
    "#9C8A5C",  # گندمی‌تیره - زیتونی
]

TEST_SKIN_TONES = {
    "روشن-خنثی (منطبق)":   "#F4DBC9",
    "روشن-زیتونی (منطبق)": "#E6DCB0",
    "متوسط-خنثی (منطبق)":  "#D9B48A",
    "متوسط-زیتونی (منطبق)": "#C2B47E",
    "زیتونی خیلی روشن (بینابین)": "#EFE2BE",
    "خنثی خیلی تیره‌تر از بازه":  "#5C3A21",
}

SCENARIOS = [
    {"name": "نور خنثی (بدون کج‌شدگی)",         "gain": (1.00, 1.00, 1.00), "gray_card": True},
    {"name": "نور گرم (زرد/تنگستن)",             "gain": (1.15, 1.00, 0.75), "gray_card": True},
    {"name": "نور سرد (آبی/ابری)",               "gain": (0.85, 1.00, 1.20), "gray_card": True},
    {"name": "نور گرم شدید - بدون کارت خاکستری", "gain": (1.25, 1.00, 0.65), "gray_card": False},
    {"name": "نور سرد شدید - بدون کارت خاکستری", "gain": (0.78, 1.00, 1.28), "gray_card": False},
]

print(f"{'سناریو':38s} | {'تناژ پوست':26s} | {'منبع تصحیح':45s} | Delta-E | Hex بازیابی‌شده")
print("-" * 150)

results = []
for scenario in SCENARIOS:
    for skin_label, skin_hex in TEST_SKIN_TONES.items():
        image, boxes = make_synthetic_swatch_image(
            skin_hex=skin_hex,
            pigment_hex=GROUND_TRUTH_PIGMENT,
            illuminant_gain=scenario["gain"],
            include_gray_card=scenario["gray_card"],
        )
        fname = f"{scenario['name']}_{skin_hex.lstrip('#')}.png".replace(" ", "_").replace("/", "-")
        save_image(image, os.path.join(OUT_DIR, fname))

        result = extract_base_pigment_color(
            image,
            skin_box=boxes["skin_box"],
            swatch_box=boxes["swatch_box"],
            gray_box=boxes.get("gray_box"),
            skin_tone_anchors=SKIN_TONE_ANCHORS,
        )

        gt_lab = rgb255_to_lab(hex_to_rgb255(GROUND_TRUTH_PIGMENT))
        dE = delta_e_76(gt_lab, result["base_pigment_lab"])

        results.append({**scenario, "skin": skin_label, "dE": dE, "hex": result["base_pigment_color"],
                         "source": result["correction_source"]})

        print(f"{scenario['name']:38s} | {skin_label:26s} | {result['correction_source']:45s} "
              f"| {dE:6.2f} | {result['base_pigment_color']}")

print("-" * 100)
all_dE = [r["dE"] for r in results]
print(f"میانگین Delta-E: {np.mean(all_dE):.2f}   |   بیشترین Delta-E: {np.max(all_dE):.2f}")
print("(راهنمای تفسیر Delta-E:  <2 تقریباً غیرقابل تشخیص با چشم   |   2-5 قابل تشخیص با دقت   |   >10 اختلاف محسوس)")

# --- تست بخش دوم: محاسبه‌ی render_color برای چند Anchor فرضی ---
print("\nنمونه محاسبه‌ی render_color برای چند Anchor فرضی (روی رنگ pigment واقعی):")
anchors = [
    {"id": 1, "reference_color": "#F5D0B0", "name": "روشن"},
    {"id": 2, "reference_color": "#C68642", "name": "متوسط"},
    {"id": 3, "reference_color": "#8D5524", "name": "تیره"},
]
for finish in ["matte", "glossy"]:
    profiles = compute_all_render_profiles(GROUND_TRUTH_PIGMENT, finish, anchors)
    print(f"  Finish={finish}:")
    for p, a in zip(profiles, anchors):
        print(f"    Anchor «{a['name']}» ({a['reference_color']}) -> {p['rendered_color']}")
