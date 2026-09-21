"""منطق استخراج رنگ روی عکس‌های مصنوعی با جواب معلوم."""
import itertools

import numpy as np
import pytest

from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab
from app.color_engine.extraction import extract_base_pigment_color
from app.color_engine.swatch_template import DEFAULT_SKIN_BOX, DEFAULT_SWATCH_BOX, to_pixels
from scripts.make_test_swatches import GRAY_BOX, make_swatch_image
from scripts.seed_demo_data import SKIN_TONE_ANCHORS

ANCHORS = [a["reference_color"] for a in SKIN_TONE_ANCHORS]
PIGMENTS = ["#B0223A", "#E0645A", "#B97A62", "#7A2E3B"]


def de(a, b):
    return delta_e_76(rgb255_to_lab(hex_to_rgb255(a)), rgb255_to_lab(hex_to_rgb255(b)))


def run(img, **kw):
    h, w = img.shape[:2]
    gray = kw.pop("gray", False)
    return extract_base_pigment_color(
        img,
        to_pixels(DEFAULT_SKIN_BOX, w, h),
        to_pixels(DEFAULT_SWATCH_BOX, w, h),
        gray_box=to_pixels(GRAY_BOX, w, h) if gray else None,
        skin_tone_anchors=ANCHORS,
        **kw,
    )


@pytest.mark.parametrize("pig", PIGMENTS)
def test_neutral_light_skin_on_anchor_is_accurate(pig):
    img = make_swatch_image("#F4DBC9", pig, "neutral")
    assert de(pig, run(img)["base_pigment_color"]) < 6


@pytest.mark.parametrize("light", ["neutral", "warm", "cool", "dim", "bright"])
def test_gray_card_plus_selected_anchor_is_robust_to_lighting(light):
    errs = []
    for pig in PIGMENTS:
        img = make_swatch_image("#D9B48A", pig, light, gray_card=True)
        r = run(img, gray=True, target_anchor_hex="#D9B48A")
        errs.append(de(pig, r["base_pigment_color"]))
    assert np.mean(errs) < 4, errs


def test_selected_anchor_fixes_dim_light_that_auto_guess_gets_wrong():
    """نور کم + پوست روشن: حدس خودکار، پوست رو «تیره‌تر» می‌فهمه؛ انتخاب دستی درسته."""
    pig = "#B0223A"
    img = make_swatch_image("#F4DBC9", pig, "dim")
    auto = de(pig, run(img)["base_pigment_color"])
    selected = de(pig, run(img, target_anchor_hex="#F4DBC9")["base_pigment_color"])
    assert selected < 4
    assert auto > selected + 5  # مستندسازی محدودیت: حدس خودکار خیلی بدتره


def test_gloss_highlight_is_ignored():
    pig = "#DC5B6B"
    img = make_swatch_image("#D9B48A", pig, "neutral", gloss_highlight=True)
    with_drop = run(img, exclude_highlights=True)
    assert with_drop["highlight_pixels_dropped"] > 0
    assert de(pig, with_drop["base_pigment_color"]) < 8


def test_warnings_for_non_uniform_swatch():
    img = make_swatch_image("#D9B48A", "#B0223A", "neutral")
    h, w = img.shape[:2]
    x0, y0, x1, y1 = to_pixels(DEFAULT_SWATCH_BOX, w, h)
    rng = np.random.default_rng(0)
    img[y0:y1, x0:x1] = rng.integers(0, 255, size=(y1 - y0, x1 - x0, 3), dtype=np.uint8)
    assert "swatch_not_uniform" in run(img)["warnings"]


def test_box_outside_image_raises():
    img = make_swatch_image("#D9B48A", "#B0223A")
    with pytest.raises(ValueError):
        extract_base_pigment_color(img, (5000, 5000, 5100, 5100), (10, 10, 50, 50), skin_tone_anchors=ANCHORS)
