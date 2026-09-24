# -*- coding: utf-8 -*-
"""
اجرای کل بک‌اند روی سیستم خودت با یک دستور — بدون Docker، Postgres و MinIO.

  دیتابیس : SQLite  (فایل local_demo.db)
  عکس‌ها  : پوشه‌ی local_storage/
  هویت    : حالت dev (خودِ صفحه هدر لازم رو می‌فرسته)

اجرا:
    cd src/back
    python -m scripts.run_local            # بعدش صفحه‌ی http://localhost:8000/review باز می‌شه
    python -m scripts.run_local --reset    # پاک کردن دیتابیس و عکس‌های قبلی و شروع از نو

فقط برای دمو/تست محلیه؛ برای تحویل نهایی از Docker + Postgres + MinIO استفاده کن.
"""
import argparse
import os
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

BACK_DIR = Path(__file__).resolve().parent.parent
os.chdir(BACK_DIR)
sys.path.insert(0, str(BACK_DIR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    db_file = BACK_DIR / "local_demo.db"
    storage_dir = BACK_DIR / "local_storage"
    if args.reset:
        db_file.unlink(missing_ok=True)
        shutil.rmtree(storage_dir, ignore_errors=True)
        print("دیتابیس و عکس‌های قبلی پاک شدن.")

    # باید قبل از import اپ تنظیم بشن (database.py موقع import می‌خونتشون)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = str(storage_dir)
    os.environ["AUTH_MODE"] = "dev"

    from app.database import Base, SessionLocal, engine
    from app import models  # noqa: F401
    from scripts.init_infra import seed_skin_tone_anchors

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_skin_tone_anchors(db)
    finally:
        db.close()

    url = f"http://localhost:{args.port}/review"
    print(f"\n>>> صفحه‌ی آپلود و بررسی: {url}\n>>> مستندات API:       http://localhost:{args.port}/docs\n")
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(url)), daemon=True).start()

    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
