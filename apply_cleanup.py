#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تمیزکاری ریپو: هرچی به فاز اول ربط نداره رو به _parked/ منتقل می‌کنه (چیزی پاک نمی‌شه).
    python apply_cleanup.py            # فقط پیش‌نمایش
    python apply_cleanup.py --apply    # واقعاً جابه‌جا می‌کنه
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARK = ROOT / "_parked"

TO_PARK = [
    "src/back/app/api", "src/back/app/core", "src/back/app/models", "src/back/app/routers",
    "src/back/app/schemas", "src/back/app/storage", "src/back/app/database.py",
    "src/back/app/static/review.html", "src/back/alembic", "src/back/alembic.ini",
    "src/back/.env.example", "src/back/Dockerfile", "docker-compose.yml", "src/database",
    "src/back/scripts/seed_demo_data.py", "src/back/scripts/upload_swatches.py",
    "src/back/scripts/run_local.py", "src/back/scripts/sample_swatches",
    "src/back/tests/test_upload_api.py", "src/live-demo",
    "src/back/app/color_engine/blend.py", "src/back/app/color_engine/texture_profiles.py",
    "src/back/app/color_engine/SPECULAR_HIGHLIGHT_SPEC.md",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    moved = skipped = 0
    for rel in TO_PARK:
        src, dst = ROOT / rel, PARK / rel
        if not src.exists():
            print(f"  -  {rel}  (وجود نداره؛ رد شد)"); skipped += 1; continue
        if dst.exists():
            print(f"  !  {rel}  (مقصد از قبل هست؛ رد شد)"); skipped += 1; continue
        print(f"  →  {rel}")
        if args.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        moved += 1
    print(f"\n{moved} مورد {'منتقل شد' if args.apply else 'منتقل می‌شه'}، {skipped} مورد رد شد.")
    if not args.apply:
        print("برای اجرای واقعی:  python apply_cleanup.py --apply")


if __name__ == "__main__":
    main()
