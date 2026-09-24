# -*- coding: utf-8 -*-
"""
آماده‌سازی زیرساخت (یک‌بار، idempotent). هیچ برند/محصول/رنگ نمونه‌ای نمی‌سازه —
رنگ‌ها فقط از سواچ‌هایی میان که خودت از /review آپلود می‌کنی.

  ۱. صبر تا Postgres آماده بشه
  ۲. ساخت جدول‌ها (Base.metadata.create_all)
  ۳. ۶ Anchor پوست (داده‌ی مرجع سیستم؛ منبعش app/anchors.py)
  ۴. ساخت bucket توی MinIO (اگه STORAGE_BACKEND=minio)

اجرا:
    cd src/back
    python -m scripts.init_infra
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401
from app.anchors import SKIN_TONE_ANCHORS  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.skin_tone_anchor import SkinToneAnchor  # noqa: E402
from app.storage import backend as storage_backend  # noqa: E402


def seed_skin_tone_anchors(db) -> int:
    """Anchorها رو با همون id های app/anchors.py می‌سازه (idها توی کد و دیتابیس یکی می‌مونن)."""
    created = 0
    for anchor in SKIN_TONE_ANCHORS:
        if db.query(SkinToneAnchor).filter(SkinToneAnchor.id == anchor["id"]).first():
            continue
        db.add(SkinToneAnchor(**anchor))
        created += 1
    db.commit()
    if db.get_bind().dialect.name == "postgresql":  # id ها رو دستی دادیم؛ sequence عقب نمونه
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('skin_tone_anchor', 'id'), (SELECT MAX(id) FROM skin_tone_anchor))"
        ))
        db.commit()
    return created


def wait_for_db(tries=30):
    for i in range(tries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:
            print(f"  Postgres هنوز آماده نیست ({i + 1}/{tries}): {type(exc).__name__}")
            time.sleep(2)
    sys.exit("به Postgres وصل نشدم — `docker compose ps` رو چک کن.")


def main():
    print("۱. اتصال به Postgres...")
    wait_for_db()
    print("   OK")

    print("۲. ساخت جدول‌ها...")
    Base.metadata.create_all(bind=engine)
    print("   OK")

    print("۳. Anchorهای پوست...")
    db = SessionLocal()
    try:
        created = seed_skin_tone_anchors(db)
    finally:
        db.close()
    print(f"   {created} تا جدید ساخته شد (بقیه از قبل بودن)")

    print("۴. MinIO bucket...")
    if storage_backend.backend() == "minio":
        from app.storage.minio_client import MINIO_BUCKET, ensure_bucket
        try:
            ensure_bucket()
            print(f"   OK (bucket: {MINIO_BUCKET})")
        except Exception as exc:
            sys.exit(f"اتصال به MinIO ناموفق بود: {exc}")
    else:
        print("   رد شد (STORAGE_BACKEND=local)")

    print("\nآماده‌ست. حالا:  uvicorn app.main:app --reload   و بعد  http://localhost:8000/review")


if __name__ == "__main__":
    main()
