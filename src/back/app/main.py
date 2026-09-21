import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (import registers all models on Base.metadata)
from app.database import get_db
from app.routers import demo, seller
from app.storage.backend import backend, local_dir

app = FastAPI(title="Virtual Try-On API")

# برای Production باید به دامنه‌ی واقعی سایت میزبان محدود بشه.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(seller.router)
app.include_router(demo.router)

# ذخیره‌ی محلی (بدون MinIO): عکس‌ها از /files سرو می‌شن
if backend() == "local":
    local_dir().mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(local_dir())), name="files")

# صفحه‌ی آپلود/بررسی برای دمو و تأیید کارفرما — فقط در حالت dev (هدر هویت ساده)
if os.getenv("AUTH_MODE", "dev") == "dev":
    @app.get("/review", include_in_schema=False)
    def review_page():
        return FileResponse(Path(__file__).parent / "static" / "review.html")


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # pragma: no cover
        db_status = f"error: {exc}"
    return {"status": "ok", "database": db_status}