# -*- coding: utf-8 -*-
"""
رندر لایو سمت بک‌اند: ماسک لب از لندمارک‌های MediaPipe + اعمال رنگ رژ به‌شکلی که
شبیه پیگمنت روی لب باشه، نه یه لایه‌ی رنگی روش.

چرا نسخه‌ی قبلی «ماسک رنگی» به نظر می‌رسید و الان چی عوض شده:

  ماسک
    (بعد از بازخورد: بیرونی به‌اندازه‌ی MASK_GROW بزرگ می‌شه تا کل لب پوشیده بشه؛ guided filter
     پیش‌فرض خاموشه چون روی عکس واقعی بخشی از لب رو بی‌رنگ می‌ذاشت)
    قبلاً: چندضلعی خام ۲۰ نقطه‌ای (لبه‌ی زاویه‌دار) + بلور یکنواخت.
    الان : منحنی نرم (Catmull-Rom) از همون لندمارک‌ها، رسم با anti-alias زیرپیکسلی،
           و لبه با guided filter روی خودِ تصویر (کانال a* و L) به مرز واقعی
           لب/پوست و لب/دندون می‌چسبه؛ فقط توی یه باند باریک دور لبه، داخل ماسک
           دست‌نخورده می‌مونه.

  رنگ
    قبلاً: فقط میانگین جابه‌جا می‌شد و L فقط ۶۰٪ (× opacity) → رنگ‌های تیره خیلی
           روشن‌تر از واقعی می‌شدن، و کل تفاوت لب‌ها (هایلایت، رگه) عیناً می‌موند.
    الان : میانگین لب کاملاً به رنگ هدف می‌رسه، و روشنایی به سه لایه شکسته می‌شه:
             ۱. سایه/حجم لب (فرکانس پایین)  → با ضریب shade_keep حفظ می‌شه
             ۲. بافت ریز (خط‌های لب)          → با ضریب detail_keep حفظ می‌شه
             ۳. هایلایت (بالاترین ۳۰٪ از L)  → براق: تقویت + کم‌رنگ‌شدن به سمت سفید،
                                              مات: تضعیف
           کروما فقط به‌اندازه‌ی chroma_keep از تنوع طبیعی لب رو نگه می‌داره تا
           لکه‌های رنگی خودِ لب زیر رژ نیفتن. دامنه‌ی سایه با روشنایی رنگ هدف مقیاس
           می‌شه (رژ تیره سایه‌ی کم‌دامنه‌تری از رژ روشن داره).

  پایداری
    LandmarkSmoother لرزش لندمارک‌ها بین فریم‌ها رو می‌گیره (تطبیقی: حرکت سریع = بدون
    تأخیر، ثابت = صاف)، تا لبه‌ی ماسک نلرزه.

پارامترهای FINISHES نقطه‌ی شروع‌ان (رجوع کن به SPECULAR_HIGHLIGHT_SPEC.md)، نه مقدار
نهایی؛ باید با چشم روی چند shade واقعی کالیبره بشن.
"""
import cv2
import numpy as np

from app.color_engine.colorspace import hex_to_rgb255, lab_to_rgb255, rgb255_to_lab

# ایندکس‌های لب توی توپولوژی ۴۶۸ نقطه‌ای FaceMesh (نقطه‌ی آخر = تکرار نقطه‌ی اول)
LIPS_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146, 61]
LIPS_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]

# opacity      : پوشش کلی (رژ مات/مایع ≈ کدر، گلاس/بالم/اویل ≈ نیمه‌شفاف)
# shade_keep   : سهم سایه/حجم طبیعی لب که حفظ می‌شه
# detail_keep  : سهم بافت ریز (خط‌های لب) که حفظ می‌شه
# chroma_keep  : سهم تنوع رنگی طبیعی لب که حفظ می‌شه
# spec         : + = تقویت هایلایت (L واحد)، − = تضعیف (مات)
# spec_desat   : چقدر هایلایت به سمت سفید (بی‌رنگ) می‌ره
FINISHES = {
    "liquid":  dict(opacity=1.00, shade_keep=0.80, detail_keep=0.85, chroma_keep=0.05, spec=-4.0, spec_desat=0.0),
    "stick":   dict(opacity=0.97, shade_keep=0.85, detail_keep=1.00, chroma_keep=0.08, spec=-2.0, spec_desat=0.0),
    "gloss":   dict(opacity=0.90, shade_keep=0.90, detail_keep=0.55, chroma_keep=0.20, spec=14.0, spec_desat=0.6),
    "balm":    dict(opacity=0.80, shade_keep=0.90, detail_keep=0.90, chroma_keep=0.30, spec=6.0, spec_desat=0.4),
    "oil":     dict(opacity=0.72, shade_keep=0.90, detail_keep=0.70, chroma_keep=0.30, spec=12.0, spec_desat=0.5),
    "plumper": dict(opacity=0.85, shade_keep=0.90, detail_keep=0.60, chroma_keep=0.20, spec=10.0, spec_desat=0.5),
}
DEFAULT_FINISH = "stick"

# پوشش ماسک: کانتور لندمارک MediaPipe معمولاً چند پیکسل «داخل» لبه‌ی واقعی لب می‌افته،
# پس بیرونی به‌اندازه‌ی MASK_GROW × عرض لب بزرگ می‌شه و دهان (دندون) کمی کوچیک‌تر.
MASK_GROW = 0.015       # نسبت به عرض لب (≈ ۲–۳ پیکسل)
FEATHER_FRAC = 0.02     # سیگمای نرمی لبه نسبت به عرض لب


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _catmull_rom_closed(pts, samples=4):
    """منحنی بسته‌ی نرم که از همه‌ی نقطه‌ها رد می‌شه. pts: Nx2 → (N*samples)x2."""
    p1 = np.asarray(pts, dtype=np.float64)
    p0, p2, p3 = np.roll(p1, 1, 0), np.roll(p1, -1, 0), np.roll(p1, -2, 0)
    t = np.linspace(0.0, 1.0, samples, endpoint=False)[:, None, None]
    out = 0.5 * (
        2 * p1
        + (-p0 + p2) * t
        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
        + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3
    )
    return np.transpose(out, (1, 0, 2)).reshape(-1, 2)


def _contour_px(landmarks_xy, idx, w, h):
    pts = np.asarray(landmarks_xy, dtype=np.float64)[idx[:-1]] * [w, h]
    return _catmull_rom_closed(pts)


def _guided_filter(guide, src, r, eps):
    """Guided filter (He et al.) با boxFilter؛ هر دو float32 در ۰..۱."""
    k = (2 * r + 1, 2 * r + 1)
    mean_i = cv2.boxFilter(guide, -1, k)
    mean_p = cv2.boxFilter(src, -1, k)
    cov_ip = cv2.boxFilter(guide * src, -1, k) - mean_i * mean_p
    var_i = cv2.boxFilter(guide * guide, -1, k) - mean_i * mean_i
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    return cv2.boxFilter(a, -1, k) * guide + cv2.boxFilter(b, -1, k)


def _norm01(x):
    lo, hi = np.percentile(x, (2, 98))
    return np.clip((x - lo) / (hi - lo + 1e-6), 0.0, 1.0).astype(np.float32)


def build_lip_alpha_mask(landmarks_xy, w, h, feather_px=None, frame_rgb=None, refine_edges=False,
                         grow_frac=MASK_GROW):
    """
    landmarks_xy: (x, y) نرمال‌شده (۰..۱) به ترتیب لندمارک‌های MediaPipe.
    grow_frac   : چقدر ماسک بیرونی رو بزرگ کنه (نسبت به عرض لب) تا کل لب پوشیده بشه.
    refine_edges: اگه True و frame_rgb داده بشه، باند لبه با guided filter تنگ‌تر می‌شه.
                  پیش‌فرض خاموشه: روی عکس واقعی گاهی بخش‌های واقعی لب رو هم می‌بُرید و
                  لب کامل رنگ نمی‌گرفت.
    خروجی: ماسک float64 هم‌اندازه‌ی تصویر (۰..۱)؛ بیرونی پر، داخلی (دهان) خالی.
    """
    outer = _contour_px(landmarks_xy, LIPS_OUTER, w, h)
    inner = _contour_px(landmarks_xy, LIPS_INNER, w, h)
    full = np.zeros((h, w), dtype=np.float64)

    lip_w = float(outer[:, 0].max() - outer[:, 0].min())
    grow = max(1, int(round(lip_w * grow_frac)))
    margin = max(8, int(lip_w * 0.15)) + grow
    x0 = max(0, int(np.floor(outer[:, 0].min())) - margin)
    y0 = max(0, int(np.floor(outer[:, 1].min())) - margin)
    x1 = min(w, int(np.ceil(outer[:, 0].max())) + margin)
    y1 = min(h, int(np.ceil(outer[:, 1].max())) + margin)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return full

    def fill(poly):
        m8 = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
        pts = np.round((poly - [x0, y0]) * 16).astype(np.int32)
        cv2.fillPoly(m8, [pts], 255, lineType=cv2.LINE_AA, shift=4)
        return m8

    def ellipse(k):
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))

    outer_m = cv2.dilate(fill(outer), ellipse(grow))
    hole_m = fill(inner)
    if grow > 1:
        hole_m = cv2.erode(hole_m, ellipse(max(1, grow // 2)))
    sigma = float(feather_px) if feather_px is not None else float(np.clip(lip_w * FEATHER_FRAC, 1.5, 4.0))
    # لبه‌ی بیرونی نرم (تا لب کامل پوشیده بشه و حس برچسب نده)، لبه‌ی داخلی (دهان/دندون)
    # تیزتر تا رنگ روی دندون نریزه
    outer_f = outer_m.astype(np.float32) / 255.0
    hole_f = hole_m.astype(np.float32) / 255.0
    if sigma > 0:
        outer_f = cv2.GaussianBlur(outer_f, (0, 0), sigma)
        hole_f = cv2.GaussianBlur(hole_f, (0, 0), max(0.8, sigma * 0.35))
    mask = np.clip(outer_f * (1.0 - hole_f), 0.0, 1.0)

    if refine_edges and frame_rgb is not None:
        lab = rgb255_to_lab(frame_rgb[y0:y1, x0:x1].astype(np.float64))
        guide = (0.7 * _norm01(lab[..., 1]) + 0.3 * _norm01(lab[..., 0])).astype(np.float32)
        r = max(2, int(round(lip_w * 0.02)))
        refined = np.clip(_guided_filter(guide, mask, r, 0.005), 0.0, 1.0)
        # عمق داخل ماسک: دور از لبه (≥ r+2 پیکسل) ماسک لندمارک دست‌نخورده؛ فقط باند لبه
        # از تصویر تصمیم می‌گیره، و فقط می‌تونه لبه رو تنگ‌تر کنه، نه بیرون‌تر
        depth = cv2.distanceTransform((mask > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
        trust = np.clip(depth / float(r + 2), 0.0, 1.0)
        mask = trust * mask + (1.0 - trust) * np.minimum(refined, mask)

    full[y0:y1, x0:x1] = mask
    return full


def blend_lip_color(frame_rgb, alpha_mask, target_hex, finish=DEFAULT_FINISH):
    """
    frame_rgb: HxWx3 uint8 (RGB). alpha_mask: خروجی build_lip_alpha_mask.
    finish: کلید FINISHES (معمولاً همون category محصول). فقط ROI دور لب پردازش می‌شه.
    """
    p = FINISHES.get(finish, FINISHES[DEFAULT_FINISH])
    ys, xs = np.nonzero(alpha_mask > 0.003)
    if len(ys) == 0:
        return frame_rgb
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1

    m = alpha_mask[y0:y1, x0:x1]
    lab = rgb255_to_lab(frame_rgb[y0:y1, x0:x1].astype(np.float64))
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]

    # «هسته‌ی» ماسک: میانگین‌ها و صدک‌ها فقط از پیکسل‌های مطمئنِ لب (نه لبه‌ی آلوده به پوست)
    core = np.where(m > 0.5, m, 0.0)
    if core.sum() < 20:
        core = m
    wsum = float(core.sum()) + 1e-9
    mean_L, mean_a, mean_b = (float((c * core).sum() / wsum) for c in (L, a, b))

    # تفکیک روشنایی به «حجم» (فرکانس پایین) و «بافت ریز»، با بلور نرمالایزشده روی هسته
    sigma = max(1.5, 0.02 * (x1 - x0))
    den = cv2.GaussianBlur(core, (0, 0), sigma) + 1e-6
    L_low = np.clip(cv2.GaussianBlur(L * core, (0, 0), sigma) / den, 0.0, 100.0)
    L_high = L - L_low

    # هایلایت: بالاترین بخش L_low داخل لب (صدک ۷۰ → ۹۸)
    hl = np.zeros_like(L)
    vals = L_low[core > 0]
    if vals.size >= 20:
        p_lo, p_hi = np.percentile(vals, (70, 98))
        if p_hi - p_lo > 3.0:
            hl = _smoothstep((L_low - p_lo) / (p_hi - p_lo))

    target_lab = rgb255_to_lab(hex_to_rgb255(target_hex))
    t_L, t_a, t_b = float(target_lab[0]), float(target_lab[1]), float(target_lab[2])

    s = float(np.clip(t_L / max(mean_L, 1.0), 0.65, 1.35))  # رژ تیره → دامنه‌ی سایه‌ی کمتر
    new_L = t_L + s * (p["shade_keep"] * (L_low - mean_L) + p["detail_keep"] * L_high) + p["spec"] * hl
    new_L = np.clip(new_L, 0.0, 100.0)
    desat = 1.0 - p["spec_desat"] * hl
    new_a = (t_a + p["chroma_keep"] * (a - mean_a)) * desat
    new_b = (t_b + p["chroma_keep"] * (b - mean_b)) * desat

    op = (m * p["opacity"])[..., None]
    new_lab = np.stack([new_L, new_a, new_b], axis=-1)
    rgb = lab_to_rgb255(lab * (1.0 - op) + new_lab * op)

    result = frame_rgb.copy()
    sel = m > 0.02
    result[y0:y1, x0:x1][sel] = rgb[sel]
    return result


class LandmarkSmoother:
    """
    فیلتر تطبیقی لرزش لندمارک‌ها (به‌جای One Euro کامل، چون فریم‌ها نامنظم می‌رسن):
    حرکت واقعی و سریع → ضریب ~۱ (بدون تأخیر)، لرزش کوچک → ضریب کم (صاف).
    یه نمونه برای هر اتصال WebSocket.
    """

    def __init__(self, min_alpha=0.35, motion_ref=0.006):
        self.min_alpha = min_alpha
        self.motion_ref = motion_ref  # میانگین حرکت (نسبت به ابعاد تصویر) که در اون alpha=۱ می‌شه
        self.prev = None

    def reset(self):
        self.prev = None

    def __call__(self, pts):
        pts = np.asarray(pts, dtype=np.float64)
        if self.prev is None or self.prev.shape != pts.shape:
            self.prev = pts
            return pts
        motion = float(np.linalg.norm(pts - self.prev, axis=1).mean())
        alpha = self.min_alpha + (1.0 - self.min_alpha) * min(1.0, motion / self.motion_ref)
        self.prev = self.prev + alpha * (pts - self.prev)
        return self.prev
