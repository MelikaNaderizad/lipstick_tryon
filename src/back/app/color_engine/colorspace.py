# -*- coding: utf-8 -*-
"""
تبدیل رنگ بین sRGB (۰-۲۵۵) و CIE Lab (D65).
پیاده‌سازی دستی با numpy، بدون نیاز به کتابخونه‌ی سنگین رنگ.
"""
import numpy as np

# نقطه‌ی سفید مرجع D65
_XN, _YN, _ZN = 0.95047, 1.00000, 1.08883

_RGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
])
_XYZ_TO_RGB = np.linalg.inv(_RGB_TO_XYZ)


def srgb_to_linear(c):
    """c: آرایه‌ی float در بازه‌ی [0,1]"""
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1 / 2.4)) - 0.055)


def rgb255_to_linear(rgb255):
    """rgb255: آرایه‌ی ...x3 با مقادیر ۰ تا ۲۵۵"""
    return srgb_to_linear(np.asarray(rgb255, dtype=np.float64) / 255.0)


def linear_to_rgb255(linear):
    srgb = linear_to_srgb(np.asarray(linear, dtype=np.float64))
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def linear_to_xyz(linear_rgb):
    return linear_rgb @ _RGB_TO_XYZ.T


def xyz_to_linear(xyz):
    return xyz @ _XYZ_TO_RGB.T


def _f(t):
    delta = 6.0 / 29.0
    return np.where(t > delta ** 3, np.cbrt(t), t / (3 * delta ** 2) + 4.0 / 29.0)


def _f_inv(t):
    delta = 6.0 / 29.0
    return np.where(t > delta, t ** 3, 3 * delta ** 2 * (t - 4.0 / 29.0))


def xyz_to_lab(xyz):
    x, y, z = xyz[..., 0] / _XN, xyz[..., 1] / _YN, xyz[..., 2] / _ZN
    fx, fy, fz = _f(x), _f(y), _f(z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return np.stack([L, a, b], axis=-1)


def lab_to_xyz(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    x = _f_inv(fx) * _XN
    y = _f_inv(fy) * _YN
    z = _f_inv(fz) * _ZN
    return np.stack([x, y, z], axis=-1)


def rgb255_to_lab(rgb255):
    return xyz_to_lab(linear_to_xyz(rgb255_to_linear(rgb255)))


def lab_to_rgb255(lab):
    return linear_to_rgb255(xyz_to_linear(lab_to_xyz(np.asarray(lab, dtype=np.float64))))


def hex_to_rgb255(hex_str):
    hex_str = hex_str.lstrip("#")
    return np.array([int(hex_str[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def rgb255_to_hex(rgb255):
    rgb255 = np.asarray(rgb255).astype(int)
    return "#{:02X}{:02X}{:02X}".format(*rgb255)


def delta_e_76(lab1, lab2):
    """ساده‌ترین معیار اختلاف رنگ ادراکی (CIE76): فاصله‌ی اقلیدسی در Lab."""
    return float(np.linalg.norm(np.asarray(lab1) - np.asarray(lab2)))
