# -*- coding: utf-8 -*-
"""
آپلود چند عکس سواچ از طریق API واقعی (بک‌اند + Postgres + MinIO باید بالا باشن) و
سنجش خروجی.

حالت ۱ — عکس‌های مصنوعی با جواب معلوم (manifest.json):
    python -m scripts.make_test_swatches
    python -m scripts.upload_swatches --dir test_swatches

حالت ۲ — عکس‌های واقعی (جواب معلوم نداریم؛ فقط رنگ استخراج‌شده چاپ می‌شه):
    python -m scripts.upload_swatches --dir my_photos --category liquid \
        --skin-box 0.10,0.30,0.45,0.70 --swatch-box 0.55,0.30,0.90,0.70

خروجی: جدول (رنگ مورد انتظار / استخراج‌شده / ΔE / هشدارها) + بررسی /demo/shades.
کد خروجی ≠ ۰ اگه هر عکسی از آستانه‌ی ΔE بدتر باشه یا بررسی‌ها خطا بدن.
"""
import argparse
import json
import mimetypes
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab  # noqa: E402

EXTS = (".jpg", ".jpeg", ".png", ".webp")


def delta_e(a_hex, b_hex):
    return delta_e_76(rgb255_to_lab(hex_to_rgb255(a_hex)), rgb255_to_lab(hex_to_rgb255(b_hex)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--user", default="test-uploader", help="مقدار هدر X-External-User-Id (AUTH_MODE=dev)")
    ap.add_argument("--category", default="liquid", help="فقط برای حالت بدون manifest")
    ap.add_argument("--skin-box"); ap.add_argument("--swatch-box"); ap.add_argument("--gray-box")
    ap.add_argument("--anchor-id", type=int)
    ap.add_argument("--mode", default="exposure", choices=["exposure", "full", "none"])
    ap.add_argument("--max-de", type=float, default=8.0, help="آستانه‌ی قبولی ΔE76 (حالت manifest)")
    args = ap.parse_args()

    base = args.api.rstrip("/")
    hdr = {"X-External-User-Id": args.user}
    c = httpx.Client(base_url=base, headers=hdr, timeout=30)
    failures = 0

    try:
        health = c.get("/health").json()
    except Exception as exc:
        sys.exit(f"بک‌اند در دسترس نیست ({base}): {exc}")
    print("health:", health)
    if health.get("database") != "ok":
        sys.exit("دیتابیس OK نیست")

    r = c.post("/seller/register", json={"business_name": "Test Uploader"})
    print("register seller:", r.status_code, "(409 یعنی از قبل بوده؛ مشکلی نیست)")

    anchors = c.get("/demo/skin-tone-anchors").json()
    if not anchors:
        sys.exit("هیچ Anchor ای توی دیتابیس نیست — اول `python -m scripts.seed_demo_data` رو اجرا کن")
    anchor_id_by_hex = {a["reference_color"].upper(): a["id"] for a in anchors}

    brand = c.post("/seller/brands", json={"name": f"Test brand {int(time.time())}", "description": "upload test"}).json()
    products = {}

    def product_for(cat):
        if cat not in products:
            pr = c.post(f"/seller/brands/{brand['id']}/products",
                        json={"name": f"Test {cat}", "category": cat, "description": ""})
            pr.raise_for_status()
            products[cat] = pr.json()["id"]
        return products[cat]

    manifest_path = os.path.join(args.dir, "manifest.json")
    if os.path.isfile(manifest_path):
        entries = json.load(open(manifest_path, encoding="utf-8"))
    else:
        files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith(EXTS))
        entries = [{"file": f, "name": os.path.splitext(f)[0], "category": args.category} for f in files]
    if not entries:
        sys.exit("عکسی پیدا نشد")

    rows, created_ids = [], []
    for e in entries:
        path = os.path.join(args.dir, e["file"])
        data = {"name": e["name"], "correction_mode": args.mode}
        for key, val in (("skin_box", args.skin_box), ("swatch_box", args.swatch_box),
                         ("gray_box", e.get("gray_box") or args.gray_box)):
            if val:
                data[key] = val
        anchor_id = args.anchor_id
        if e.get("selected_anchor_hex"):
            anchor_id = anchor_id_by_hex.get(e["selected_anchor_hex"].upper(), anchor_id)
        if anchor_id:
            data["skin_tone_anchor_id"] = str(anchor_id)

        ctype = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as fh:
            resp = c.post(f"/seller/products/{product_for(e['category'])}/shades",
                          data=data, files={"swatch": (e["file"], fh, ctype)})
        if resp.status_code != 201:
            failures += 1
            rows.append((e["name"], e.get("expected_color", "-"), f"HTTP {resp.status_code}", None, resp.text[:80], None))
            continue
        shade = resp.json()
        created_ids.append(shade["id"])
        got = shade["base_pigment_color"]
        warns = ",".join(shade["extraction_meta"].get("warnings", [])) or "-"
        exp = e.get("expected_color")
        de = delta_e(exp, got) if exp else None
        limit = e.get("known_limit")
        if de is not None and de > args.max_de and not limit:
            failures += 1
        rows.append((e["name"], exp or "-", got, de, warns, limit))

    print(f"\n{'نام':32s} {'مورد انتظار':12s} {'استخراج':10s} {'ΔE76':>6s}  هشدار")
    for name, exp, got, de, warns, limit in rows:
        if de is None:
            mark = ""
        elif de <= args.max_de:
            mark = "  ✓"
        else:
            mark = "  ⚠ محدودیت شناخته‌شده: " + limit if limit else "  ✗"
        print(f"{name:32s} {exp:12s} {got:10s} {('%.1f' % de) if de is not None else '-':>6s}  {warns}{mark}")

    # ---- بررسی لایه‌ی خوانا برای دموی لایو ----
    print("\nبررسی /demo/shades ...")
    listed = {s["id"]: s for s in c.get("/demo/shades").json()}
    for sid in created_ids:
        s = listed.get(sid)
        if s is None:
            failures += 1
            print(f"  ✗ shade {sid} توی /demo/shades نیست")
            continue
        ok_profiles = len(s["render_profiles"]) == len(anchors)
        url = s["swatch_image_url"]
        url_status = "null"
        if url:
            try:
                url_status = httpx.get(url if url.startswith("http") else base + url, timeout=10).status_code
            except Exception as exc:
                url_status = f"خطا: {type(exc).__name__}"
        print(f"  shade {sid}: render_profiles={len(s['render_profiles'])}/{len(anchors)} "
              f"{'✓' if ok_profiles else '✗'}  swatch_url={url_status}")
        if not ok_profiles:
            failures += 1

    print("\nنتیجه:", "همه‌چی OK" if failures == 0 else f"{failures} مورد مشکل داشت")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
