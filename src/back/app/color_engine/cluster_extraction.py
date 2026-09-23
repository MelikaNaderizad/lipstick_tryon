# -*- coding: utf-8 -*-
"""
استخراج رنگ غالب سواچ با خوشه‌بندی (KMeans روی فضای Lab)، بدون نیاز به کادر ثابت.

برخلاف extraction.py (که فرض می‌کرد سواچ دقیقاً توی یه کادر مشخص از عکسه)،
این نسخه کل عکس رو خوشه‌بندی می‌کنه و خوشه‌ای که بیشترین «کروما» (رنگ‌غلظت) رو
داره به‌عنوان پیگمنت رژ انتخاب می‌شه — چون رژ (هر رنگی، حتی آبی/سبز/بنفش)
تقریباً همیشه از پوست/پس‌زمینه‌ی اطرافش پررنگ‌تره.

منبع: پورت شده از پروژه‌ی خواهر «agent» (app/core/color_extract.py).
تفاوت با عکس‌های قالب‌دار (Swatch Template): اینجا محل قرارگیری رژ روی عکس
مهم نیست، فقط باید واقعاً پررنگ‌تر از اطرافش باشه.

⚠️ محدودیت شناخته‌شده (متفاوت با extraction.py):
    این نسخه هیچ تصحیح نوری نداره (نه کارت خاکستری، نه Anchor پوست). زیر نور
    رنگی (گرم/سرد) ΔE می‌تونه به ۱۰-۱۸ برسه (در extraction.py با تصحیح، زیر ۴).
    در عوض، برخلاف extraction.py، به جای دقیق سواچ روی عکس حساس نیست.
⚠️ محدودیت دوم: برای رژهای خیلی کم‌کروما (نودی/مات ملایم)، اگه لکه‌ی
    قرمزی روی پوست (بند انگشت، برافروختگی) بیشتر از ~۳٪ مساحت عکس باشه،
    ممکنه به‌جای رژ واقعی انتخاب بشه (چون کروما بالاتری داره).
"""
import math

import cv2
import numpy as np
from sklearn.cluster import KMeans


def _bgr_to_lab_channels(img_bgr):
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_ch = img_lab[:, :, 0] * (100.0 / 255.0)
    a_ch = img_lab[:, :, 1] - 128.0
    b_ch = img_lab[:, :, 2] - 128.0
    return l_ch, a_ch, b_ch


def extract_dominant_swatch_color(image_bgr, k: int = 5, min_cluster_fraction: float = 0.03,
                                  top_vivid_fraction: float = 0.08):
    """
    ورودی: تصویر BGR (خروجی cv2.imread یا cv2.cvtColor(rgb, RGB2BGR)).
    top_vivid_fraction: به‌جای میانگین کل خوشه‌ی برنده، فقط از پررنگ‌ترین این
    درصد پیکسل‌های همون خوشه میانگین می‌گیریم (لبه‌ی سواچ معمولاً محوتره).
    """
    h, w = image_bgr.shape[:2]
    scale = 300 / max(h, w)
    if scale < 1:
        image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)))

    l_ch, a_ch, b_ch = _bgr_to_lab_channels(image_bgr)
    pixels = np.stack([l_ch, a_ch, b_ch], axis=-1).reshape(-1, 3)

    kmeans = KMeans(n_clusters=k, n_init=4, random_state=42)
    labels = kmeans.fit_predict(pixels)
    centers = kmeans.cluster_centers_

    total_pixels = len(labels)
    clusters_info = []
    for i in range(k):
        idx_mask = labels == i
        count = int(np.sum(idx_mask))
        fraction = count / total_pixels
        l, a, b = centers[i]
        chroma = float(np.sqrt(a ** 2 + b ** 2))
        hue_deg = math.degrees(math.atan2(b, a))
        clusters_info.append({
            "cluster_id": i, "fraction": fraction,
            "lab": {"l": float(l), "a": float(a), "b": float(b)},
            "chroma": chroma, "hue_deg": hue_deg, "_pixel_mask": idx_mask,
        })

    valid_clusters = [c for c in clusters_info if c["fraction"] >= min_cluster_fraction]
    if not valid_clusters:
        valid_clusters = clusters_info

    swatch_cluster = max(valid_clusters, key=lambda c: c["chroma"])

    cluster_pixels = pixels[swatch_cluster["_pixel_mask"]]
    cl, ca, cb = cluster_pixels[:, 0], cluster_pixels[:, 1], cluster_pixels[:, 2]
    cluster_chroma = np.sqrt(ca ** 2 + cb ** 2)
    n_top = max(1, int(len(cluster_chroma) * top_vivid_fraction))
    top_idx = np.argsort(-cluster_chroma)[:n_top]
    vivid_lab = {"l": float(cl[top_idx].mean()), "a": float(ca[top_idx].mean()), "b": float(cb[top_idx].mean())}

    for c in clusters_info:
        del c["_pixel_mask"]

    warnings = []
    if swatch_cluster["fraction"] < 0.02:
        warnings.append("swatch_fraction_small")  # سواچ کمتر از ۲٪ عکس؛ نتیجه ممکنه نویزی باشه
    if swatch_cluster["chroma"] < 12:
        warnings.append("low_chroma_swatch")  # رژ کم‌رنگه؛ ریسک اشتباه گرفتن با قرمزی پوست بیشتره

    return {
        "swatch_lab": vivid_lab,
        "swatch_fraction": swatch_cluster["fraction"],
        "swatch_chroma": swatch_cluster["chroma"],
        "warnings": warnings,
        "all_clusters": sorted(clusters_info, key=lambda c: -c["chroma"]),
    }


def lab_to_hex(lab: dict) -> str:
    lab_px = np.array([[[lab["l"] * 255.0 / 100.0, lab["a"] + 128.0, lab["b"] + 128.0]]], dtype=np.uint8)
    r, g, b = cv2.cvtColor(lab_px, cv2.COLOR_LAB2RGB)[0, 0]
    return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
