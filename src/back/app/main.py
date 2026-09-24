# -*- coding: utf-8 -*-
"""
بک‌اند: آپلود سواچ، استخراج رنگ (GrabCut + Lab)، تأیید فروشنده، و ارائه‌ی رنگ‌های
تأییدشده به دموی لایو — همه از پشت Postgres + MinIO (روترهای /seller و /demo).

اجرا:
    cd src/back
    uvicorn app.main:app --reload
بعد http://localhost:8000/review (آپلود/بررسی سواچ) یا http://localhost:8000/docs.
برای پیش‌نمایش لایو با دوربین: src/live-demo/index.html رو مستقیم توی مرورگر باز
کن (رنگ‌های approved رو از همین بک‌اند می‌گیره؛ نیازی به سرو شدن از اینجا نداره).

نکته: مسیر سبک/بدون-دیتابیس قبلی (extract.html، /extract، /apply، /extractions*،
/anchors، store.py، lip_apply.py) حذف شد — حالا که دیتابیس آماده‌ست، /review +
/seller مسیر اصلی‌ان. اگه این فایل‌ها هنوز توی چک‌اوت شمان، remove_legacy_files.py
رو از ریشه‌ی ریپو اجرا کن.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import SessionLocal
from app.routers import demo, seller
from app.storage import backend as storage_backend

app = FastAPI(title="Lipstick swatch color extraction")

# برای live-demo که از یه origin دیگه صدا می‌زنه؛ توی production محدودش کن
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(seller.router)
app.include_router(demo.router)

if storage_backend.backend() == "local":  # فقط وقتی STORAGE_BACKEND=local
    storage_backend.local_dir().mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=storage_backend.local_dir()), name="files")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "database": db_status}


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/review")


@app.get("/review", include_in_schema=False)
def review():
    return FileResponse(STATIC_DIR / "review.html")
