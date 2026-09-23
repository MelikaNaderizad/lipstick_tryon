# -*- coding: utf-8 -*-
"""
هسته‌ی مینیمال فاز اول: آپلود عکس سواچ (با دو کادرِ خودِ فروشنده: پوست + رژ)
→ استخراج رنگ خالص رژ، به‌علاوه‌ی پیش‌نمایش اپلای رنگ روی لب برای یه عکس چهره.

بدون Auth، بدون دیتابیس، بدون MinIO. اجرا:
    cd src/back
    uvicorn app.main:app --reload
بعد http://localhost:8000/ (صفحه‌ی آپلود) یا http://localhost:8000/docs

روش استخراج رنگ: فروشنده خودش دو کادر می‌کشه — یکی روی پوست خالی (دست/مچ)،
یکی دقیقاً روی رژِ کشیده‌شده. رنگ از میانه‌ی پیکسل‌های کادر رژ (در فضای خطی)
به‌دست میاد، پس هرچی بیرون کادر باشه (آستین، پس‌زمینه، انگشت) روی نتیجه اثر
نمی‌ذاره. جزئیات: app/color_engine/extraction.py

روش قبلی (خوشه‌بندی بدون کادر، app/color_engine/cluster_extraction.py) هنوز
توی کد هست ولی دیگه پیش‌فرض نیست — چون بدون کادر، اگه توی فریم چیز پررنگ‌تری
از خودِ رژ باشه (مثلاً آستین قرمز)، ممکنه اون رو به‌جای رژ انتخاب کنه.
"""
import re
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.anchors import SKIN_TONE_ANCHORS, anchor_by_id
from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab
from app.color_engine.extraction import extract_base_pigment_color
from app.color_engine.swatch_template import parse_box, to_pixels
from app.imaging import ImageError, decode_image
from app.lip_apply import NoFaceDetected, apply_lipstick_to_image
from app.store import ResultStore

app = FastAPI(title="Lipstick swatch color extraction")

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
STATIC_DIR = Path(__file__).parent / "static"


def _rgb_to_bgr(rgb_array: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)


def _read_upload(upload: UploadFile):
    if upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "فقط JPEG/PNG/WebP قبول می‌شه")
    raw = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "حجم فایل بیشتر از ۱۰ مگابایته")
    try:
        image, img_meta = decode_image(raw)
    except ImageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return raw, image, img_meta, ALLOWED_TYPES[upload.content_type]


def _parse_required_box(text, field):
    if text is None or text.strip() == "":
        raise HTTPException(422, f"{field} لازمه — کادرش رو روی عکس بکش")
    try:
        return parse_box(text)
    except ValueError as exc:
        raise HTTPException(422, f"{field}: {exc}")


def _parse_optional_box(text, field):
    if text is None or text.strip() == "":
        return None
    try:
        return parse_box(text)
    except ValueError as exc:
        raise HTTPException(422, f"{field}: {exc}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "extract.html")


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
    عکس سواچ + دو کادر (کسری ۰..۱: 'x0,y0,x1,y1') → رنگ خالص رژ. کادر رژ باید
    کاملاً داخل رنگ رژ باشه؛ هرچی خارج این دو کادره (آستین، پس‌زمینه) بی‌اثره.
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

    raw, image, img_meta, ext = _read_upload(swatch)
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
    delta_e = None
    if expected:
        delta_e = round(delta_e_76(rgb255_to_lab(hex_to_rgb255(expected)), rgb255_to_lab(hex_to_rgb255(color))), 2)

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
    _, image, _, _ = _read_upload(photo)

    lab = rgb255_to_lab(hex_to_rgb255(color))
    target_lab = {"l": float(lab[0]), "a": float(lab[1]), "b": float(lab[2])}

    try:
        result_bgr = apply_lipstick_to_image(_rgb_to_bgr(image), target_lab)
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
