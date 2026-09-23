# -*- coding: utf-8 -*-
"""
اپلای رنگ رژ روی لب توی یه عکس ثابت (نه لایو): تشخیص لندمارک لب با MediaPipe
+ ترکیب رنگ در فضای Lab (کانال a/b عوض می‌شه، L عمدتاً حفظ می‌شه تا بافت/های‌لایت
طبیعی لب از بین نره).

منبع: پورت شده از پروژه‌ی خواهر «agent» (app/core/face_landmarks.py +
app/core/color_lab.py). دقیقاً همون منطقیه که قبلاً توی src/live-demo/index.html
(نسخه‌ی جاوااسکریپت/لایو) پیاده شده بود؛ اینجا معادل سروری/پایتونی‌ش برای عکس
ثابته (مثلاً برای پیش‌نمایش سمت seller، نه دوربین زنده).

نکته‌ی نصب: mediapipe==0.10.13 توصیه شده (نسخه‌های 0.10.30+ دیگه mp.solutions
قدیمی رو ندارن). این ماژول فقط موقع صدا زدن apply_lipstick_to_image ایمپورت
می‌شه، نه در import ماژول — تا اگه mediapipe نصب نباشه، بقیه‌ی برنامه (استخراج
رنگ) بدون خطا کار کنه.
"""
import cv2
import numpy as np

_LIP_OUTER_IDX = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
_LIP_INNER_IDX = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]


class NoFaceDetected(ValueError):
    pass


def _get_lip_contours(image_bgr):
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh
    with mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True) as face_mesh:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None
        landmarks = results.multi_face_landmarks[0]

    h, w = image_bgr.shape[:2]

    def to_px(idx_list):
        return [(int(landmarks.landmark[i].x * w), int(landmarks.landmark[i].y * h)) for i in idx_list]

    return {"outer": to_px(_LIP_OUTER_IDX), "inner": to_px(_LIP_INNER_IDX)}


def _build_lip_mask(image_shape, contours, feather_px=4):
    h, w = image_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(contours["outer"], dtype=np.int32)], 255)
    cv2.fillPoly(mask, [np.array(contours["inner"], dtype=np.int32)], 0)
    if feather_px > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=feather_px)
    return mask.astype(np.float32) / 255.0


def _apply_color_to_masked_region(image_bgr, mask, target_lab, blend_ratio=0.95, l_blend_ratio=0.25):
    img_lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_ch = img_lab[:, :, 0] * (100.0 / 255.0)
    a_ch = img_lab[:, :, 1] - 128.0
    b_ch = img_lab[:, :, 2] - 128.0

    alpha = mask * blend_ratio
    new_a = a_ch * (1 - alpha) + target_lab["a"] * alpha
    new_b = b_ch * (1 - alpha) + target_lab["b"] * alpha

    l_alpha = mask * blend_ratio * l_blend_ratio
    new_l = l_ch * (1 - l_alpha) + target_lab["l"] * l_alpha

    out_lab = np.stack([new_l * (255.0 / 100.0), new_a + 128.0, new_b + 128.0], axis=-1)
    out_lab = np.clip(out_lab, 0, 255).astype(np.uint8)
    return cv2.cvtColor(out_lab, cv2.COLOR_LAB2BGR)


def apply_lipstick_to_image(image_bgr, target_lab: dict, feather_px=4, blend_ratio=0.95, l_blend_ratio=0.25):
    """
    image_bgr: خروجی cv2.imread (یا cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)).
    target_lab: {"l":..., "a":..., "b":...} — رنگ رژی که می‌خوای روی لب بشینه.
    خروجی: تصویر BGR با لب رنگ‌شده. NoFaceDetected اگه چهره‌ای پیدا نشه.
    """
    contours = _get_lip_contours(image_bgr)
    if contours is None:
        raise NoFaceDetected("چهره‌ای در عکس تشخیص داده نشد")
    mask = _build_lip_mask(image_bgr.shape, contours, feather_px=feather_px)
    return _apply_color_to_masked_region(image_bgr, mask, target_lab, blend_ratio, l_blend_ratio)
