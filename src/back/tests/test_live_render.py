"""رندر لایو روی لب مصنوعی با جواب معلوم (بدون MediaPipe و دیتابیس)."""
import numpy as np
import pytest

from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab
from app.color_engine.live_render import (
    FINISHES, LIPS_INNER, LIPS_OUTER, LandmarkSmoother, blend_lip_color, build_lip_alpha_mask,
)

W, H, CX, CY = 480, 360, 240, 220


def _landmarks(inset=0):
    """inset: لندمارک‌ها چند پیکسل «داخل» لبه‌ی واقعی لب (مثل چهره‌ی واقعی)."""
    pts = np.zeros((478, 2))
    for idx, rx, ry in ((LIPS_OUTER, 90 - inset, 38 - inset), (LIPS_INNER, 70 + inset, 10 - inset)):
        n = len(idx) - 1
        for k, i in enumerate(idx[:-1]):
            t = 2 * np.pi * k / n
            pts[i] = ((CX + rx * np.cos(t)) / W, (CY + ry * np.sin(t)) / H)
    return pts


def _frame(seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    img = np.zeros((H, W, 3))
    img[:] = (224, 172, 150)
    outer = (((xx - CX) / 90) ** 2 + ((yy - CY) / 38) ** 2) < 1
    inner = (((xx - CX) / 70) ** 2 + ((yy - CY) / 10) ** 2) < 1
    lip = outer & ~inner
    tex = 1 + 0.08 * np.sin(xx * 0.9) * np.cos(yy * 0.3) + rng.normal(0, 0.03, (H, W))
    img[lip] = (np.array([190, 90, 100.]) * tex[..., None])[lip]
    img[inner] = (240, 240, 235)
    return np.clip(img + rng.normal(0, 1.5, img.shape), 0, 255).astype(np.uint8), lip, inner


def _lab(px):
    return rgb255_to_lab(px.astype(np.float64))


@pytest.mark.parametrize("finish", ["liquid", "stick"])
@pytest.mark.parametrize("target", ["#B0223A", "#7A2E3B", "#E0645A"])
def test_opaque_finish_reaches_target_color(finish, target):
    img, lip, _ = _frame()
    mask = build_lip_alpha_mask(_landmarks(), W, H, frame_rgb=img)
    out = blend_lip_color(img, mask, target, finish)
    core = mask > 0.95
    mean = _lab(out[core]).mean(0)
    assert delta_e_76(mean, rgb255_to_lab(hex_to_rgb255(target))) < 8


def test_lip_texture_is_preserved_not_flattened():
    img, _, _ = _frame()
    mask = build_lip_alpha_mask(_landmarks(), W, H, frame_rgb=img)
    out = blend_lip_color(img, mask, "#B0223A", "stick")
    core = mask > 0.95
    assert _lab(out[core])[:, 0].std() > 1.5  # ماسک تخت std≈۰ می‌داد


def test_pixels_outside_lips_and_teeth_are_untouched():
    img, lip, inner = _frame()
    mask = build_lip_alpha_mask(_landmarks(), W, H, frame_rgb=img)
    out = blend_lip_color(img, mask, "#B0223A", "stick")
    yy, xx = np.mgrid[0:H, 0:W]
    far_skin = (((xx - CX) / 90) ** 2 + ((yy - CY) / 38) ** 2) > 1.6
    assert np.abs(out[far_skin].astype(int) - img[far_skin].astype(int)).max() <= 6  # فقط دنباله‌ی نامحسوس feather
    deep_teeth = (((xx - CX) / 70) ** 2 + ((yy - CY) / 10) ** 2) < 0.5
    assert np.abs(out[deep_teeth].astype(int) - img[deep_teeth].astype(int)).max() <= 4


def test_mask_edge_is_antialiased_and_inner_hole_is_empty():
    img, _, _ = _frame()
    mask = build_lip_alpha_mask(_landmarks(), W, H, frame_rgb=img)
    assert ((mask > 0.05) & (mask < 0.95)).any()      # لبه‌ی نرم، نه پله‌ای
    assert mask[CY, CX] < 0.05                         # وسط دهان (دندون) رنگ نمی‌گیره
    assert mask[CY + 25, CX] > 0.95                    # خودِ لب کامل پوشیده


def test_lips_are_fully_covered_even_when_landmarks_sit_inside_the_edge():
    img, lip, _ = _frame()
    mask = build_lip_alpha_mask(_landmarks(inset=2), W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    almost_all_lip = lip & (((xx - CX) / 88) ** 2 + ((yy - CY) / 36) ** 2 < 1)  # ۲px داخل‌تر از لبه
    assert (mask[almost_all_lip] > 0.5).mean() > 0.98
    out = blend_lip_color(img, mask, "#B0223A", "stick")
    d = np.abs(out.astype(int) - img.astype(int)).sum(-1)
    assert (d[almost_all_lip] > 20).mean() > 0.95    # واقعاً رنگ گرفتن، نه فقط ماسک


def test_gloss_has_brighter_highlight_than_matte():
    img, _, _ = _frame()
    yy, xx = np.mgrid[0:H, 0:W]
    hl = np.exp(-(((xx - CX + 20) / 25) ** 2 + ((yy - CY - 18) / 4) ** 2))[..., None]
    lip = (((xx - CX) / 90) ** 2 + ((yy - CY) / 38) ** 2 < 1) & ~(((xx - CX) / 70) ** 2 + ((yy - CY) / 10) ** 2 < 1)
    img = np.where(lip[..., None], img * (1 - 0.5 * hl) + 127 * hl, img).astype(np.uint8)
    mask = build_lip_alpha_mask(_landmarks(), W, H, frame_rgb=img)
    top = lambda o: np.percentile(_lab(o[mask > 0.95])[:, 0], 99)
    assert top(blend_lip_color(img, mask, "#DC5B6B", "gloss")) > top(blend_lip_color(img, mask, "#DC5B6B", "liquid")) + 6


def test_unknown_finish_falls_back_and_no_lips_is_noop():
    img, _, _ = _frame()
    mask = build_lip_alpha_mask(_landmarks(), W, H, frame_rgb=img)
    assert blend_lip_color(img, mask, "#B0223A", "nonsense").shape == img.shape
    assert blend_lip_color(img, np.zeros((H, W)), "#B0223A") is img
    assert set(FINISHES) >= {"liquid", "stick", "gloss", "balm", "oil", "plumper"}


def test_smoother_damps_jitter_but_follows_real_motion():
    pts = _landmarks()
    s = LandmarkSmoother()
    s(pts)
    jit = s(pts + 0.001)
    assert np.abs(jit - pts).max() < 0.001            # لرزش کوچک نصف‌شده
    s2 = LandmarkSmoother()
    s2(pts)
    moved = s2(pts + 0.05)
    assert np.abs(moved - (pts + 0.05)).max() < 1e-6  # حرکت واقعی بدون تأخیر
