# -*- coding: utf-8 -*-
"""
بک‌اند: استخراج رنگ سواچ (دو کادر: پوست + رژ) + پیش‌نمایش اپلای روی لب،
به‌علاوه‌ی لایه‌ی Postgres + MinIO (روترهای /seller و /demo و صفحه‌ی /review).

اجرا:
    cd src/back
    uvicorn app.main:app --reload
بعد http://localhost:8000/review (آپلود سواچ به MinIO/Postgres)،
http://localhost:8000/ (استخراج ساده بدون دیتابیس + پیش‌نمایش روی لب) یا http://localhost:8000/docs
"""
from pathlib import Path

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.anchors import SKIN_TONE_ANCHORS, anchor_by_id
from app.color_engine.colorspace import delta_e_hex, hex_to_rgb255, rgb255_to_lab
from app.color_engine.extraction import extract_base_pigment_color
from app.color_engine.swatch_template import parse_box, to_pixels
from app.database import SessionLocal
from app.lip_apply import NoFaceDetected, apply_lipstick_to_image
from app.routers import demo, seller
from app.storage import backend as storage_backend
from app.store import ResultStore
from app.uploads import HEX_RE, read_upload

app = FastAPI(title="Lipstick swatch color extraction")

# برای live-demo که از یه origin دیگه صدا می‌زنه؛ توی production محدودش کن
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(seller.router)
app.include_router(demo.router)

if storage_backend.backend() == "local":  # فقط وقتی STORAGE_BACKEND=local
    storage_backend.local_dir().mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=storage_backend.local_dir()), name="files")

STATIC_DIR = Path(__file__).parent / "static"


def _parse_required_box(text_value, field):
    if text_value is None or text_value.strip() == "":
        raise HTTPException(422, f"{field} لازمه — کادرش رو روی عکس بکش")
    try:
        return parse_box(text_value)
    except ValueError as exc:
        raise HTTPException(422, f"{field}: {exc}")


def _parse_optional_box(text_value, field):
    if text_value is None or text_value.strip() == "":
        return None
    try:
        return parse_box(text_value)
    except ValueError as exc:
        raise HTTPException(422, f"{field}: {exc}")


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
    return FileResponse(STATIC_DIR / "extract.html")


@app.get("/review", include_in_schema=False)
def review():
    return FileResponse(STATIC_DIR / "review.html")


@app.get("/anchors")
def list_anchors():
    return SKIN_TONE_ANCHORS


@app.post("/extract")
def extract(
    swatch: UploadFile = File(...),
    name: str = Form(""),
    skin_box: str = Form(...),
    swatch_box: str = Form(...),
    gray_box: str | None = Form(None),
    anchor_id: int | None = Form(None),
    correction_mode: str = Form("none"),
    expected_color: str | None = Form(None),
    save: bool = Form(True),
):
    """
    ابزار سبک بدون دیتابیس: عکس سواچ + دو کادر (کسری ۰..۱: 'x0,y0,x1,y1') → رنگ خالص رژ.
    نتیجه فقط توی فایل JSON (src/back/data) ذخیره می‌شه؛ آپلود به Postgres/MinIO از /seller/... انجام می‌شه.
    correction_mode='none' یعنی همون رنگ خام کادر، بدون تصحیح نور.
    """
    if correction_mode not in ("none", "exposure", "full"):
        raise HTTPException(422, "correction_mode باید none یا exposure یا full باشه")
    expected = (expected_color or "").strip() or None
    if expected and not HEX_RE.match(expected):
        raise HTTPException(422, "expected_color باید #RRGGBB باشه")

    anchor = None
    if anchor_id is not None:
        anchor = anchor_by_id(anchor_id)
        if anchor is None:
            raise HTTPException(422, "anchor_id نامعتبره")

    skin_frac = _parse_required_box(skin_box, "skin_box")
    swatch_frac = _parse_required_box(swatch_box, "swatch_box")
    gray_frac = _parse_optional_box(gray_box, "gray_box")

    raw, image, img_meta, ext = read_upload(swatch)
    h, w = image.shape[:2]
    try:
        result = extract_base_pigment_color(
            image,
            to_pixels(skin_frac, w, h),
            to_pixels(swatch_frac, w, h),
            gray_box=to_pixels(gray_frac, w, h) if gray_frac else None,
            skin_tone_anchors=[a["reference_color"] for a in SKIN_TONE_ANCHORS],
            target_anchor_hex=anchor["reference_color"] if anchor else None,
            correction_mode=correction_mode,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    color = result["base_pigment_color"]
    delta_e = round(delta_e_hex(expected, color), 2) if expected else None

    record = {
        "name": name.strip() or swatch.filename or "swatch",
        "base_pigment_color": color,
        "expected_color": expected.upper() if expected else None,
        "delta_e": delta_e,
        "warnings": result["warnings"],
        "params": {
            "anchor_id": anchor_id,
            "correction_mode": correction_mode,
            "boxes_fraction": {"skin": skin_frac, "swatch": swatch_frac, "gray": gray_frac},
        },
        "image": {"width": w, "height": h, **img_meta},
        "extraction": result,
    }
    if save:
        try:
            record = ResultStore().add(record, raw, ext)
        except OSError as exc:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"ذخیره‌ی نتیجه ناموفق بود: {exc}")
        record["image_url"] = f"/extractions/{record['id']}/image"
    else:
        record = {"id": None, "image_url": None, **record}
    return record


@app.post("/apply")
def apply_lipstick(
    photo: UploadFile = File(...),
    color: str = Form(...),
):
    """عکس چهره + رنگ (#RRGGBB) → همون عکس با رژ روی لب (پیش‌نمایش، نه لایو)."""
    if not HEX_RE.match(color):
        raise HTTPException(422, "color باید #RRGGBB باشه")
    _, image, _, _ = read_upload(photo)

    lab = rgb255_to_lab(hex_to_rgb255(color))
    target_lab = {"l": float(lab[0]), "a": float(lab[1]), "b": float(lab[2])}

    try:
        result_bgr = apply_lipstick_to_image(cv2.cvtColor(image, cv2.COLOR_RGB2BGR), target_lab)
    except NoFaceDetected as exc:
        raise HTTPException(422, str(exc))
    except ImportError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "mediapipe نصب نیست — pip install mediapipe==0.10.13",
        )

    ok, buf = cv2.imencode(".jpg", result_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise HTTPException(500, "ساخت عکس نتیجه ناموفق بود")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.get("/extractions")
def list_extractions():
    items = ResultStore().list()
    for r in items:
        r["image_url"] = f"/extractions/{r['id']}/image"
    return items


@app.get("/extractions/{rid}")
def get_extraction(rid: str):
    rec = ResultStore().get(rid)
    if rec is None:
        raise HTTPException(404, "پیدا نشد")
    rec["image_url"] = f"/extractions/{rid}/image"
    return rec


@app.get("/extractions/{rid}/image")
def get_extraction_image(rid: str):
    path = ResultStore().image_path(rid)
    if path is None:
        raise HTTPException(404, "پیدا نشد")
    return FileResponse(path)


@app.delete("/extractions/{rid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extraction(rid: str):
    if not ResultStore().delete(rid):
        raise HTTPException(404, "پیدا نشد")
