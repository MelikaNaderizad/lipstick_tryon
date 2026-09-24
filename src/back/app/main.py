# -*- coding: utf-8 -*-
"""
بک‌اند: آپلود سواچ، استخراج رنگ (GrabCut + Lab)، تأیید فروشنده، ارائه‌ی رنگ‌های
تأییدشده به دموی لایو، و حالا خودِ حالت لایو (WebSocket + MediaPipe پایتون) —
همه از پشت Postgres + MinIO (روترهای /seller، /demo، /ws/live-tryon).

اجرا:
    cd src/back
    uvicorn app.main:app --reload
بعد http://localhost:8000/review (آپلود/بررسی سواچ)، http://localhost:8000/live
(پیش‌نمایش لایو با دوربین — صفحه‌ی موقت توی همین static، تا فرانت اصلی بیاد بالا)
یا http://localhost:8000/docs.

نکته: مسیر سبک/بدون-دیتابیس قبلی (extract.html، /extract، /apply، /extractions*،
/anchors، store.py، lip_apply.py) حذف شد — حالا که دیتابیس آماده‌ست، /review +
/seller مسیر اصلی‌ان. اگه این فایل‌ها هنوز توی چک‌اوت شمان، remove_legacy_files.py
رو از ریشه‌ی ریپو اجرا کن.

نکته‌ی دوم: حالت لایو قبلاً کاملاً سمت مرورگر بود (MediaPipe JS + blend رنگ در
JS، توی src/live-demo/index.html و بخش پیش‌نمایش لایو review.html). حالا با
تصمیم صریح، لندمارک لب و ترکیب رنگ هر دو رفتن بک‌اند (app/routers/live.py):
کلاینت هر فریم رو با WebSocket می‌فرسته، سرور با MediaPipe پایتون رنگش می‌کنه
و برمی‌گردونه. src/live-demo/index.html و بخش قدیمی review.html فعلاً دست‌نخورده
موندن (تا فرانت اصلی جایگزین بشه)؛ صفحه‌ی جدید /live مسیر توصیه‌شده‌ست.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import SessionLocal
from app.routers import demo, live, seller
from app.storage import backend as storage_backend

app = FastAPI(title="Lipstick swatch color extraction")

# برای live-demo/فرانت آینده که از یه origin دیگه صدا می‌زنه؛ توی production محدودش کن
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(seller.router)
app.include_router(demo.router)
app.include_router(live.router)

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


@app.get("/live", include_in_schema=False)
def live_page():
    return FileResponse(STATIC_DIR / "live.html")
