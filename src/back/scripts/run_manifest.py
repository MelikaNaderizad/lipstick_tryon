# -*- coding: utf-8 -*-
"""
اجرای موتور رنگ روی یه پوشه عکس، مستقیم (بدون سرور) — حلقه‌ی سریع برای کار روی منطق.

حالت ۱ — عکس‌های مصنوعی با جواب معلوم:
    python -m scripts.make_test_swatches
    python -m scripts.run_manifest --dir test_swatches

حالت ۲ — عکس‌های واقعی خودت. یه manifest.json کنار عکس‌ها بذار (فقط "file" لازمه؛
بقیه اختیاری) تا ΔE هم حساب بشه:
    [{"file": "rose1.jpg", "name": "Rose", "expected_color": "#B0223A",
      "selected_anchor_hex": "#F4DBC9", "gray_box": "0.02,0.02,0.14,0.14",
      "skin_box": "0.1,0.3,0.45,0.7", "swatch_box": "0.55,0.3,0.9,0.7"}]
اگه manifest نباشه، همه‌ی عکس‌های پوشه با کادرهای پیش‌فرض اجرا می‌شن.

کد خروجی ≠ ۰ اگه عکسی (بدون known_limit) از آستانه‌ی ΔE بدتر باشه.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.anchors import SKIN_TONE_ANCHORS  # noqa: E402
from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab  # noqa: E402
from app.color_engine.extraction import extract_base_pigment_color  # noqa: E402
from app.color_engine.swatch_template import (  # noqa: E402
    DEFAULT_SKIN_BOX, DEFAULT_SWATCH_BOX, parse_box, to_pixels,
)
from app.imaging import decode_image  # noqa: E402

EXTS = (".jpg", ".jpeg", ".png", ".webp")


def delta_e(a_hex, b_hex):
    return delta_e_76(rgb255_to_lab(hex_to_rgb255(a_hex)), rgb255_to_lab(hex_to_rgb255(b_hex)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="test_swatches")
    ap.add_argument("--mode", default="exposure", choices=["exposure", "full", "none"])
    ap.add_argument("--max-de", type=float, default=8.0, help="آستانه‌ی قبولی ΔE76")
    args = ap.parse_args()

    manifest_path = os.path.join(args.dir, "manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            entries = json.load(fh)
    else:
        entries = [{"file": f, "name": os.path.splitext(f)[0]}
                   for f in sorted(os.listdir(args.dir)) if f.lower().endswith(EXTS)]
    if not entries:
        sys.exit("عکسی پیدا نشد")

    anchors = [a["reference_color"] for a in SKIN_TONE_ANCHORS]
    failures = 0
    print(f"{'نام':30s} {'مورد انتظار':12s} {'استخراج':10s} {'ΔE76':>6s}  هشدار / منبع تصحیح")
    for e in entries:
        with open(os.path.join(args.dir, e["file"]), "rb") as fh:
            image, _ = decode_image(fh.read())
        h, w = image.shape[:2]
        skin = parse_box(e["skin_box"]) if e.get("skin_box") else DEFAULT_SKIN_BOX
        swatch = parse_box(e["swatch_box"]) if e.get("swatch_box") else DEFAULT_SWATCH_BOX
        gray = parse_box(e["gray_box"]) if e.get("gray_box") else None
        r = extract_base_pigment_color(
            image, to_pixels(skin, w, h), to_pixels(swatch, w, h),
            gray_box=to_pixels(gray, w, h) if gray else None,
            skin_tone_anchors=anchors,
            target_anchor_hex=e.get("selected_anchor_hex"),
            correction_mode=args.mode,
        )
        exp = e.get("expected_color")
        de = delta_e(exp, r["base_pigment_color"]) if exp else None
        limit = e.get("known_limit")
        if de is None:
            mark = ""
        elif de <= args.max_de:
            mark = "  ✓"
        elif limit:
            mark = "  ⚠ محدودیت شناخته‌شده: " + limit
        else:
            mark = "  ✗"
            failures += 1
        warns = ",".join(r["warnings"]) or "-"
        print(f"{e.get('name', e['file']):30s} {exp or '-':12s} {r['base_pigment_color']:10s} "
              f"{('%.1f' % de) if de is not None else '-':>6s}  {warns} | {r['correction_source']}{mark}")

    print("\nنتیجه:", "همه‌چی OK" if failures == 0 else f"{failures} مورد از آستانه بدتر بود")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
