# -*- coding: utf-8 -*-
"""
حالت لایو با WebSocket — همه‌چی (لندمارک لب + ترکیب رنگ) سمت بک‌اند.

پروتکل:
  ۱. کلاینت وصل می‌شه به  /ws/live-tryon
  ۲. هر وقت خواست، یه پیام متنی JSON برای تنظیم رنگ/فینیش می‌فرسته:
         {"target_color": "#RRGGBB", "finish": "gloss"}      (هر دو اختیاری)
     finish یکی از کلیدهای FINISHES (liquid|stick|gloss|balm|oil|plumper) ـه.
  ۳. برای هر فریم، یه پیام باینری (JPEG) می‌فرسته. سرور فریم رنگ‌شده رو
     (یا فریم خام اگه چهره‌ای پیدا نشه) به‌صورت باینری (JPEG) برمی‌گردونه.

نکته: چون MediaPipe FaceMesh thread-safe نیست، برای هر اتصال یه نمونه‌ی
جدا ساخته می‌شه و موقع قطع اتصال بسته می‌شه. پردازش سنگین (MediaPipe + رنگ +
JPEG) توی thread جدا اجرا می‌شه تا event loop قفل نشه؛ فریم‌های یه اتصال پشت
سر هم پردازش می‌شن (هیچ‌وقت دو فراخوانی هم‌زمان روی یه FaceMesh نداریم).
"""
import asyncio
import json

import cv2
import mediapipe as mp
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.color_engine.live_render import (
    DEFAULT_FINISH,
    FINISHES,
    LandmarkSmoother,
    blend_lip_color,
    build_lip_alpha_mask,
)
from app.uploads import HEX_RE

router = APIRouter(tags=["live"])

_JPEG_QUALITY = 80
_DEFAULT_COLOR = "#B0223A"


def _decode_jpeg(data: bytes):
    arr = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _encode_jpeg(rgb):
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
    return buf.tobytes() if ok else None


def _process_frame(face_mesh, smoother, data: bytes, target_hex: str, finish: str):
    """decode → لندمارک → ماسک → رنگ → encode. sync؛ با asyncio.to_thread صدا زده می‌شه."""
    frame_rgb = _decode_jpeg(data)
    if frame_rgb is None:
        return None
    h, w = frame_rgb.shape[:2]
    result = face_mesh.process(frame_rgb)
    if result.multi_face_landmarks:
        pts = np.array([(p.x, p.y) for p in result.multi_face_landmarks[0].landmark])
        pts = smoother(pts)
        mask = build_lip_alpha_mask(pts, w, h)
        out = blend_lip_color(frame_rgb, mask, target_hex, finish)
    else:
        smoother.reset()
        out = frame_rgb  # چهره‌ای پیدا نشد؛ فریم خام برمی‌گرده
    return _encode_jpeg(out)


@router.websocket("/ws/live-tryon")
async def live_tryon(ws: WebSocket):
    await ws.accept()
    target_hex = _DEFAULT_COLOR
    finish = DEFAULT_FINISH
    smoother = LandmarkSmoother()
    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break

            text = message.get("text")
            if text is not None:
                try:
                    cfg = json.loads(text)
                except ValueError:
                    continue
                if not isinstance(cfg, dict):
                    continue
                color = cfg.get("target_color")
                if isinstance(color, str) and HEX_RE.match(color):
                    target_hex = color.upper()
                fin = cfg.get("finish")
                if fin in FINISHES:
                    finish = fin
                continue

            data = message.get("bytes")
            if not data:
                continue

            encoded = await asyncio.to_thread(_process_frame, face_mesh, smoother, data, target_hex, finish)
            if encoded:
                await ws.send_bytes(encoded)
    except WebSocketDisconnect:
        pass
    finally:
        face_mesh.close()
