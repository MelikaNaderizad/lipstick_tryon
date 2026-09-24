"""لکه‌ی رژ روی دست با ضخامت متغیر (نازک در لبه، ضخیم در وسط) — همون شرایط واقعی."""
import numpy as np
import pytest

from app.color_engine.colorspace import (
    delta_e_76, hex_to_rgb255, linear_to_rgb255, rgb255_to_lab, rgb255_to_linear,
)
from app.color_engine.extraction import extract_base_pigment_color

SKIN_BOX = (560, 450, 760, 560)
SWATCH_BOX = (130, 180, 500, 520)  # مستطیل شل دور لکه


def de(a, b):
    return delta_e_76(rgb255_to_lab(hex_to_rgb255(a)), rgb255_to_lab(hex_to_rgb255(b)))


def make_smear(pig_hex, skin=(238, 200, 175), amax=1.0, plateau=0.5, gloss=False, w=800, h=600, seed=0):
    """observed = α·pigment + (1-α)·skin در فضای خطی؛ α از لبه (۰) تا وسط (amax)."""
    rng = np.random.default_rng(seed)
    skin_l = rgb255_to_linear(np.array(skin, float))
    pig_l = rgb255_to_linear(hex_to_rgb255(pig_hex))
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    p0, p1 = np.array([180, 470.]), np.array([440, 250.])
    d = p1 - p0
    t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / (d ** 2).sum(), 0, 1)
    dist = np.hypot(xx - (p0[0] + t * d[0]), yy - (p0[1] + t * d[1]))
    prof = np.clip((1 - dist / 45.0) / (1 - plateau), 0, 1)
    prof = prof * prof * (3 - 2 * prof)
    a = (amax * prof)[..., None]
    img = a * pig_l + (1 - a) * skin_l
    if gloss:
        blob = np.exp(-(((xx - 310) / 12) ** 2 + ((yy - 360) / 12) ** 2))[..., None]
        img = img * (1 - 0.8 * blob) + 0.72 * blob
    rgb = linear_to_rgb255(img).astype(float) + rng.normal(0, 2, (h, w, 3))
    return np.clip(rgb, 0, 255).astype(np.uint8)


def run(img, **kw):
    return extract_base_pigment_color(img, SKIN_BOX, SWATCH_BOX, correction_mode="none", **kw)


@pytest.mark.parametrize("pig", ["#B0223A", "#E0645A", "#B97A62", "#7A2E3B", "#3A5FCD"])
def test_thick_center_of_smear_gives_pigment_not_skin_mix(pig):
    r = run(make_smear(pig))
    assert de(pig, r["base_pigment_color"]) < 4
    assert r["opaque_median_distance_from_skin"] > 12


def test_gloss_highlight_does_not_hijack_thickest_layer():
    r = run(make_smear("#DC5B6B", gloss=True))
    assert de("#DC5B6B", r["base_pigment_color"]) < 5


def test_sheer_product_needs_opacity_input():
    pig = "#B0223A"
    img = make_smear(pig, amax=0.5)
    assert de(pig, run(img)["base_pigment_color"]) > 20                 # بدون α: به پوست کج می‌شه
    assert de(pig, run(img, opacity=0.5)["base_pigment_color"]) < 10    # با α: unmixing درست می‌کنه


def test_ramp_without_plateau_warns():
    r = run(make_smear("#B0223A", plateau=0.0))
    assert "swatch_may_be_sheer" in r["warnings"]


def test_box_on_bare_skin_falls_back():
    img = make_smear("#B0223A")
    r = extract_base_pigment_color(img, SKIN_BOX, (580, 460, 740, 540), correction_mode="none")
    assert "swatch_pigment_not_found" in r["warnings"]
