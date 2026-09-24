# -*- coding: utf-8 -*-
"""
حذف مسیر سبک/بدون-دیتابیس (extract.html + store.py + lip_apply.py + test_api.py).

این مسیر فقط برای ارائه‌ی ماژولار به کارفرما، قبل از آماده شدن Postgres/MinIO،
ساخته شده بود. حالا که دیتابیس آماده‌ست، /review + /seller + src/live-demo مسیر
اصلی‌ان و این فایل‌ها اضافه‌ان.

اجرا از ریشه‌ی ریپو:
    python remove_legacy_files.py            # پیش‌نمایش (dry-run)
    python remove_legacy_files.py --apply    # حذف واقعی (قبلش commit بگیر)

Idempotent: اگه فایلی از قبل نباشه، بدون خطا رد می‌شه.

قبل از اجرا، این‌ها رو از زیپ جایگزین کن (تغییر کردن، نه فقط حذف):
    src/back/app/main.py           بدون /, /anchors, /extract, /apply, /extractions*
    src/back/requirements.txt      بدون خط mediapipe==0.10.13
    src/back/tests/conftest.py     بدون fixture مخصوص TRYON_DATA_DIR
    src/live-demo/index.html       ماسک لب با feather (لبه‌ی نرم‌تر)
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES_TO_REMOVE = [
    "src/back/app/static/extract.html",
    "src/back/app/store.py",
    "src/back/app/lip_apply.py",
    "src/back/tests/test_api.py",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="واقعاً حذف کن (پیش‌فرض: فقط نشون بده)")
    args = ap.parse_args()

    print("مسیر سبک/بدون-دیتابیس دیگه لازم نیست؛ /review + /seller + src/live-demo مسیر اصلی‌ان.\n")
    print("در حال حذف:" if args.apply else "این فایل‌ها حذف خواهند شد (dry-run؛ با --apply واقعاً حذف کن):")
    removed = 0
    for rel in FILES_TO_REMOVE:
        p = ROOT / rel
        if not p.is_file():
            print(f"  - {rel}  (از قبل نیست، رد شد)")
            continue
        print(f"  - {rel}")
        if args.apply:
            p.unlink()
            removed += 1

    if args.apply:
        print(f"\n{removed} فایل حذف شد.")
    print("\nیادت نره از زیپ جایگزین کنی: app/main.py، requirements.txt، tests/conftest.py، src/live-demo/index.html.")


if __name__ == "__main__":
    main()
