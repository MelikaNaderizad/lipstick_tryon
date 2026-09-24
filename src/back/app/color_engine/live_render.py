# -*- coding: utf-8 -*-
"""
رندر لایو سمت بک‌اند: ساخت ماسک لب از لندمارک‌های MediaPipe و ترکیب رنگ در
فضای Lab. پورت پایتونی همون منطقی که قبلاً توی src/live-demo/index.html و
بخش پیش‌نمایش لایو review.html با JS اجرا می‌شد (همون ثابت‌ها و همون
ایندکس‌های لب، تا رنگ نهایی با نسخه‌ی قبلی و با شبیه‌سازی استاتیک
color_engine/blend.py هم‌خوان بمونه).

اجرا سمت سرور (نه شیدر/کلاینت) یعنی هر فریم رفت‌وبرگشت شبکه داره؛ برای
حالت واقعاً real-time (۳۰fps) لتنسی محسوسه — این یه تصمیم عمدیه، نه محدودیت
ناخواسته (رجوع کن به تصمیم پروژه: منطق لایو سمت بک‌اند).
"""
import cv2
import numpy as np

from app.color_engine.blend import BASE_OPACITY
from app.color_engine.colorspace import hex_to_rgb255, lab_to_rgb255, rgb255_to_lab

# همون ایندکس‌های review.html / src/live-demo — توپولوژی ۴۶۸ نقطه‌ای FaceMesh
# و FaceLandmarker (Tasks API) یکیه، پس این لیست‌ها بین دو پیاده‌سازی مشترکن.
LIPS_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146, 61]
LIPS_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]

L_BLEND_RATIO = 0.6    # سهم جابه‌جایی روشنایی (بقیه‌ش رو کنتراست/بافت طبیعی لب نگه می‌داره)
FEATHER_PX = 6          # نرمی لبه‌ی ماسک (بزرگ‌تر از قبل تا لبه حس «برچسب» نده)


def build_lip_alpha_mask(landmarks_xy, w, h, feather_px=FEATHER_PX):
    """
    landmarks_xy: دنباله‌ای از (x, y) نرمال‌شده (۰..۱)، به ترتیب همون ۴۶۸ لندمارک
    MediaPipe (result.multi_face_landmarks[0].landmark).
    خروجی: ماسک float64 هم‌اندازه‌ی تصویر (۰..۱) — بیرونی پر، داخلی خالی (evenodd)، فدرشده.
    """
    pts = np.asarray(landmarks_xy, dtype=np.float64)
    outer = (pts[LIPS_OUTER] * [w, h]).astype(np.int32).reshape((-1, 1, 2))
    inner = (pts[LIPS_INNER] * [w, h]).astype(np.int32).reshape((-1, 1, 2))

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [outer], 255)
    cv2.fillPoly(mask, [inner], 0)  # معادل قانون evenodd: تو رو دوباره خالی کن

    if feather_px > 0:
        k = feather_px * 2 + 1
        mask = cv2.GaussianBlur(mask, (k, k), feather_px)
    return mask.astype(np.float64) / 255.0


def blend_lip_color(frame_rgb, alpha_mask, target_hex, base_opacity=BASE_OPACITY, l_blend_ratio=L_BLEND_RATIO):
    """
    frame_rgb: HxWx3 uint8 (RGB). alpha_mask: HxW فلوت ۰..۱ (خروجی build_lip_alpha_mask).
    فقط پیکسل‌های داخل ماسک محاسبه می‌شن (سرعت).

    به‌جای blend خطی به‌سمت یه رنگ ثابت (که واریانس/بافت طبیعی لب رو صاف
    می‌کنه و حس «ماسک رنگی» می‌ده)، اینجا انتقال رنگ (color transfer) انجام
    می‌شه: میانگین رنگ خودِ لب کاربر در Lab حساب می‌شه، بعد فقط همون میانگین
    به‌سمت رنگ هدف جابه‌جا می‌شه (shift ثابت روی همه‌ی پیکسل‌ها). اختلاف هر
    پیکسل از میانگین (های‌لایت، سایه، خط‌های لب) دست‌نخورده می‌مونه، پس زیر
    رنگ جدید هم دیده می‌شه — نتیجه شبیه پیگمنت روی لب واقعیه، نه یه لایه‌ی
    یکدست روش. وزن هر پیکسل (alpha_mask × base_opacity) هم روی شدت shift
    اثر می‌ذاره، نه روی فشرده‌کردن واریانس؛ برای همین لبه‌ی فدرشده هم طبیعی
    محو می‌شه، نه کم‌رنگ.
    """
    ys, xs = np.nonzero(alpha_mask > 0.003)
    if len(ys) == 0:
        return frame_rgb

    weight = alpha_mask[ys, xs] * base_opacity
    region = frame_rgb[ys, xs].astype(np.float64)
    lab = rgb255_to_lab(region)
    target_lab = rgb255_to_lab(hex_to_rgb255(target_hex))

    mean_lab = np.average(lab, axis=0, weights=weight)
    shift = target_lab - mean_lab  # (dL, da, db) — فقط میانگین جابه‌جا می‌شه

    l_weight = weight * l_blend_ratio  # روشنایی با سهم کمتر جابه‌جا می‌شه (کنتراست طبیعی لب حفظ بشه)
    new_lab = lab.copy()
    new_lab[:, 0] = lab[:, 0] + shift[0] * l_weight
    new_lab[:, 1] = lab[:, 1] + shift[1] * weight
    new_lab[:, 2] = lab[:, 2] + shift[2] * weight

    out_rgb = lab_to_rgb255(new_lab)
    result = frame_rgb.copy()
    result[ys, xs] = out_rgb
    return result
