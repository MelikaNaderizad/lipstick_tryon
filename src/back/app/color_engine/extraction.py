# -*- coding: utf-8 -*-
"""
پایپ‌لاین استخراج رنگ خالص رژ (base_pigment_color) از عکس Swatch با دو کادر
دستی (پوست خالی + رژ).

مدل فیزیکی: رژ روی پوست نیمه‌شفافه، پس رنگ دیده‌شده در فضای linear RGB ترکیبیه:

    observed = α · pigment + (1 − α) · skin

پس برای گرفتن رنگ خالص باید اثر پوست رو حذف کنیم. سه مرحله:

  ۱. جداسازی: GrabCut پیکسل‌های «غیرپوست» داخل کادر رژ رو پیدا می‌کنه (کادر
     پوست به‌عنوان پس‌زمینه‌ی قطعی بهش داده می‌شه). فقط روی ناحیه‌ی دور دو کادر
     و با رزولوشن کاهش‌یافته اجرا می‌شه (سریع).
  ۲. حذف پوست با انتخاب ضخیم‌ترین لایه: لکه‌ی رژ روی دست از وسط ضخیمه و از
     لبه‌ها نازک (α کم). پیکسل‌هایی که در فضای Lab بیشترین فاصله رو از رنگ
     پوست (کادر پوست، بعد از تصحیح نور) دارن، همون‌هایی‌ان که α≈۱ دارن؛ رنگ
     اون‌ها تقریباً خودِ پیگمنته و نیازی به حدس α نیست.
  ۳. (اختیاری) اگه محصول ذاتاً شفافه (α<۱ حتی در ضخیم‌ترین لایه)، فروشنده α رو
     می‌ده و فرمول unmixing اعمال می‌شه: pigment = (observed − (1−α)·skin) / α.
     α رو نمی‌شه از یه عکس تنها درآورد؛ باید ورودی باشه.

اگه GrabCut چیزی به‌عنوان پیگمنت پیدا نکنه، به کل کادر برمی‌گرده و هشدار می‌ده.
"""
import cv2
import numpy as np

from app.color_engine.colorspace import (
    rgb255_to_linear, linear_to_rgb255, rgb255_to_lab, hex_to_rgb255, rgb255_to_hex,
)

_LAST_RESORT_SKIN_HEX = "#C68642"
_LAST_RESORT_SKIN_LINEAR = rgb255_to_linear(hex_to_rgb255(_LAST_RESORT_SKIN_HEX))

_GRABCUT_ITERATIONS = 5
_MIN_FOREGROUND_PIXELS = 20
_GRABCUT_MAX_SIDE = 300     # ضلع بلندتر ROI قبل از GrabCut به این مقدار کاهش می‌یابد
_ROI_MARGIN = 0.15          # حاشیه‌ی دور اتحاد دو کادر (نسبت به ابعاد اتحاد)

DEFAULT_PLATEAU_RATIO = 0.85  # پیکسل‌هایی که فاصله‌شون از پوست ≥ ۰.۸۵ × (صدک ۹۰ام) باشه = «پلاتوی کدر»
_LAB_WEIGHTS = np.array([0.5, 1.0, 1.0])  # وزن L کمتر تا سایه/هایلایت جای رنگ رو نگیره
_MIN_PLATEAU_SHARE = 0.30   # اگه کمتر از این سهم پیکسل‌ها به پلاتو برسن، لکه کدر نمی‌شه → احتمالاً شفاف
_CLOSE_TO_SKIN_DE = 12.0    # رژ خیلی نزدیک به پوست (نودی روی پوست) → اطمینان کمتر


def _weighted_target_from_anchors(skin_lab_L, anchor_hex_list, tier_tolerance=6.0):
    scored = [
        (abs(rgb255_to_lab(hex_to_rgb255(h).astype(np.float64))[0] - skin_lab_L), h)
        for h in anchor_hex_list
    ]
    scored.sort(key=lambda t: t[0])
    nearest_diff = scored[0][0]
    same_tier = [h for diff, h in scored if diff <= nearest_diff + tier_tolerance]
    target_linear = np.mean([rgb255_to_linear(hex_to_rgb255(h)) for h in same_tier], axis=0)
    source = "skin_tone_anchor_tier_avg:" + "+".join(same_tier)
    return target_linear, source


def crop(image, box):
    x0, y0, x1, y1 = box
    return image[y0:y1, x0:x1, :]


def _robust_linear_mean(patch_rgb255):
    linear = rgb255_to_linear(patch_rgb255).reshape(-1, 3)
    return np.median(linear, axis=0)


def estimate_illuminant_gain(skin_patch_rgb255, gray_patch_rgb255=None, skin_tone_anchors=None,
                             target_anchor_hex=None, mode="exposure"):
    if gray_patch_rgb255 is not None:
        gray_linear = _robust_linear_mean(gray_patch_rgb255)
        target = np.mean(gray_linear)
        gain = np.clip(target / np.clip(gray_linear, 1e-6, None), 0.4, 2.5)
        source = "gray_card"
        if target_anchor_hex and mode != "none":
            skin_wb = _robust_linear_mean(skin_patch_rgb255) * gain
            y_w = np.array([0.2126729, 0.7151522, 0.0721750])
            t_lin = rgb255_to_linear(hex_to_rgb255(target_anchor_hex))
            scale = float(t_lin @ y_w) / max(float(skin_wb @ y_w), 1e-6)
            gain = gain * np.clip(scale, 0.4, 2.5)
            source = "gray_card+selected_anchor_exposure"
        return gain, source

    skin_linear = _robust_linear_mean(skin_patch_rgb255)

    if mode == "none":
        return np.ones(3), "none"

    if target_anchor_hex:
        target_linear = rgb255_to_linear(hex_to_rgb255(target_anchor_hex))
        source = "selected_anchor:" + target_anchor_hex
    elif skin_tone_anchors:
        skin_lab_L = rgb255_to_lab(linear_to_rgb255(skin_linear).astype(np.float64))[0]
        target_linear, source = _weighted_target_from_anchors(skin_lab_L, skin_tone_anchors)
    else:
        target_linear = _LAST_RESORT_SKIN_LINEAR
        source = "last_resort_constant"

    if mode == "exposure":
        y_w = np.array([0.2126729, 0.7151522, 0.0721750])
        scale = float(target_linear @ y_w) / max(float(skin_linear @ y_w), 1e-6)
        gain = np.full(3, np.clip(scale, 0.4, 2.5))
        return gain, source + "|exposure_only"

    gain = target_linear / np.clip(skin_linear, 1e-6, None)
    gain = np.clip(gain, 0.4, 2.5)
    return gain, source + "|full"


def _drop_highlights(pixels_rgb255, margin_L=12.0):
    """pixels_rgb255: آرایه‌ی Nx3. پیکسل‌های خیلی روشن‌تر از میانه (برق گلاس) رو کنار می‌ذاره."""
    L = rgb255_to_lab(pixels_rgb255)[:, 0]
    keep = L <= np.median(L) + margin_L
    if keep.sum() < 20:
        return pixels_rgb255, 0
    return pixels_rgb255[keep], int((~keep).sum())


def _scaled_box(box, ox, oy, scale, max_w, max_h):
    """مختصات کادر (تصویر کامل) → مختصات ROI کاهش‌یافته؛ حداقل ۱ پیکسل و داخل مرز."""
    x0, y0, x1, y1 = box
    sx0 = min(max(int(round((x0 - ox) * scale)), 0), max_w - 1)
    sy0 = min(max(int(round((y0 - oy) * scale)), 0), max_h - 1)
    sx1 = min(max(int(round((x1 - ox) * scale)), sx0 + 1), max_w)
    sy1 = min(max(int(round((y1 - oy) * scale)), sy0 + 1), max_h)
    return sx0, sy0, sx1, sy1


def _grabcut_foreground_mask(image_rgb255, swatch_box, skin_box, iterations=_GRABCUT_ITERATIONS):
    """
    GrabCut فقط روی ROI دور دو کادر و با رزولوشن کاهش‌یافته. کادر پوست پس‌زمینه‌ی
    قطعی (GC_BGD) ـه. خروجی: ماسک بولی هم‌اندازه‌ی تصویر کامل (فقط داخل کادر رژ)،
    یا None اگه GrabCut چیزی پیدا نکرد.
    """
    h, w = image_rgb255.shape[:2]
    x0, y0, x1, y1 = swatch_box
    sx0, sy0, sx1, sy1 = skin_box

    ux0, uy0, ux1, uy1 = min(x0, sx0), min(y0, sy0), max(x1, sx1), max(y1, sy1)
    mx, my = int((ux1 - ux0) * _ROI_MARGIN), int((uy1 - uy0) * _ROI_MARGIN)
    rx0, ry0 = max(0, ux0 - mx), max(0, uy0 - my)
    rx1, ry1 = min(w, ux1 + mx), min(h, uy1 + my)
    roi = image_rgb255[ry0:ry1, rx0:rx1]
    rh, rw = roi.shape[:2]

    scale = min(1.0, _GRABCUT_MAX_SIDE / max(rh, rw))
    if scale < 1.0:
        small_w, small_h = max(2, int(round(rw * scale))), max(2, int(round(rh * scale)))
        small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_AREA)
    else:
        small = roi
    sh, sw = small.shape[:2]
    sc_x, sc_y = sw / rw, sh / rh
    scale_used = min(sc_x, sc_y)

    b_sw = _scaled_box(swatch_box, rx0, ry0, scale_used, sw, sh)
    b_sk = _scaled_box(skin_box, rx0, ry0, scale_used, sw, sh)

    mask = np.full((sh, sw), cv2.GC_PR_BGD, dtype=np.uint8)
    mask[b_sw[1]:b_sw[3], b_sw[0]:b_sw[2]] = cv2.GC_PR_FGD
    mask[b_sk[1]:b_sk[3], b_sk[0]:b_sk[2]] = cv2.GC_BGD

    small_bgr = cv2.cvtColor(small, cv2.COLOR_RGB2BGR)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(small_bgr, mask, None, bgd_model, fgd_model, iterations, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None

    fg_small = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    if scale_used < 1.0:
        fg_roi = cv2.resize(fg_small, (rw, rh), interpolation=cv2.INTER_NEAREST).astype(bool)
    else:
        fg_roi = fg_small.astype(bool)

    fg_full = np.zeros((h, w), dtype=bool)
    fg_full[ry0:ry1, rx0:rx1] = fg_roi
    box_mask = np.zeros((h, w), dtype=bool)
    box_mask[y0:y1, x0:x1] = True
    fg_full &= box_mask
    if int(fg_full.sum()) < _MIN_FOREGROUND_PIXELS:
        return None
    return fg_full


def _select_opaque_pixels(fg_lab, skin_lab, plateau_ratio=DEFAULT_PLATEAU_RATIO):
    """
    ضخیم‌ترین لایه‌ی رژ = «پلاتوی» فاصله از پوست: پیکسل‌هایی که فاصله‌ی (وزن‌دار)
    Lab‌شون از پوست حداقل plateau_ratio × صدک ۹۰ام باشه (α≈۱).
    نسبت ثابتِ صدک (مثلاً «۳۰٪ دورترین») روی سواچ کدر و بافت‌دار، تیره‌ترین
    شیارهای بافت رو انتخاب می‌کرد و رنگ رو تیره‌تر از واقعی می‌داد؛ این روش روی
    سواچ یکدست تقریباً کل سواچ رو نگه می‌داره و فقط روی لکه‌ی نازک‌شونده حاشیه رو
    حذف می‌کنه. خروجی: (اندیس‌ها، dict اطلاعات).
    """
    d = np.linalg.norm((fg_lab - skin_lab) * _LAB_WEIGHTS, axis=1)
    d_ref = float(np.percentile(d, 90))
    keep = d >= plateau_ratio * d_ref
    if int(keep.sum()) < 20:
        keep = np.zeros(len(d), dtype=bool)
        keep[np.argsort(-d)[:min(len(d), 20)]] = True
    idx = np.flatnonzero(keep)
    return idx, {
        "opaque_pixels_used": int(len(idx)),
        "opaque_median_distance_from_skin": round(float(np.median(d[idx])), 2),
        "opaque_plateau_share": round(float(keep.mean()), 3),
    }


def extract_base_pigment_color(image_rgb255, skin_box, swatch_box, gray_box=None, skin_tone_anchors=None,
                               target_anchor_hex=None, correction_mode="exposure", opacity=None,
                               exclude_highlights=True, plateau_ratio=DEFAULT_PLATEAU_RATIO):
    """
    opacity: None = کدر فرض می‌شه (α=۱ در ضخیم‌ترین لایه؛ بدون unmixing).
             عدد بین ۰.۳ تا ۱ = پوشش ذاتی محصول → unmixing با فرمول بالا.
    """
    skin_patch = crop(image_rgb255, skin_box)
    full_swatch_patch = crop(image_rgb255, swatch_box)
    gray_patch = crop(image_rgb255, gray_box) if gray_box else None
    warnings = []

    if skin_patch.size == 0 or full_swatch_patch.size == 0:
        raise ValueError("کادر پوست یا سواچ خالیه (مختصات خارج از تصویر)")

    fg_mask = _grabcut_foreground_mask(image_rgb255, swatch_box, skin_box)
    if fg_mask is None:
        # GrabCut چیزی پیدا نکرد (مثلاً کادر رژ اشتباهاً روی پوست خالی کشیده شده)
        fg_pixels = full_swatch_patch.reshape(-1, 3)
        excluded_fraction = 0.0
        warnings.append("swatch_pigment_not_found")
    else:
        fg_pixels = image_rgb255[fg_mask]
        box_area = full_swatch_patch.shape[0] * full_swatch_patch.shape[1]
        excluded_fraction = float(1.0 - fg_mask.sum() / box_area)

    n_dropped = 0
    if exclude_highlights:
        fg_pixels, n_dropped = _drop_highlights(fg_pixels)

    gain, correction_source = estimate_illuminant_gain(
        skin_patch, gray_patch, skin_tone_anchors,
        target_anchor_hex=target_anchor_hex, mode=correction_mode,
    )

    skin_linear = _robust_linear_mean(skin_patch)
    skin_corr = skin_linear * gain
    fg_linear_corr = np.clip(rgb255_to_linear(fg_pixels) * gain, 0.0, 1.0)

    skin_lab = rgb255_to_lab(linear_to_rgb255(skin_corr).astype(np.float64))
    fg_lab = rgb255_to_lab(linear_to_rgb255(fg_linear_corr).astype(np.float64))

    idx, opaque_info = _select_opaque_pixels(fg_lab, skin_lab, plateau_ratio)
    swatch_linear_raw = _robust_linear_mean(fg_pixels[idx])
    swatch_corr = np.median(fg_linear_corr[idx], axis=0)

    opacity_used = 1.0
    if opacity is not None and opacity < 1.0:
        opacity_used = float(np.clip(opacity, 0.3, 1.0))
        swatch_corr = (swatch_corr - (1 - opacity_used) * skin_corr) / opacity_used

    corrected_linear = np.clip(swatch_corr, 0.0, 1.0)
    corrected_rgb255 = linear_to_rgb255(corrected_linear)
    corrected_lab = rgb255_to_lab(corrected_rgb255.astype(np.float64))

    if np.any(np.isclose(gain, 0.4)) or np.any(np.isclose(gain, 2.5)):
        warnings.append("lighting_correction_clamped")
    if float(np.max(np.std(fg_lab[idx], axis=0))) > 12.0:
        warnings.append("swatch_not_uniform")
    if len(fg_pixels) < 400:
        warnings.append("swatch_patch_small")
    if float(np.max(swatch_corr)) >= 0.999:
        warnings.append("swatch_overexposed")
    if float(np.max(swatch_linear_raw)) < 0.01:
        warnings.append("swatch_too_dark")
    if excluded_fraction > 0.4:
        warnings.append("swatch_box_loosely_cropped")
    if fg_mask is not None:
        if opaque_info["opaque_median_distance_from_skin"] < _CLOSE_TO_SKIN_DE:
            warnings.append("swatch_close_to_skin")
        elif opacity is None and opaque_info["opaque_plateau_share"] < _MIN_PLATEAU_SHARE:
            warnings.append("swatch_may_be_sheer")

    return {
        "base_pigment_color": rgb255_to_hex(corrected_rgb255),
        "base_pigment_lab": corrected_lab.tolist(),
        "illuminant_gain": np.asarray(gain).tolist(),
        "correction_source": correction_source,
        "raw_swatch_color": rgb255_to_hex(linear_to_rgb255(swatch_linear_raw)),
        "skin_color_corrected": rgb255_to_hex(linear_to_rgb255(skin_corr)),
        "opacity_used": round(opacity_used, 3),
        "highlight_pixels_dropped": n_dropped,
        "vivid_pixels_excluded_fraction": round(excluded_fraction, 3),
        **opaque_info,
        "warnings": warnings,
    }
