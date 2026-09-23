import io
import struct

import numpy as np
import pytest
from PIL import Image, ImageCms

from app.imaging import ImageError, decode_image


def png(img, **save_kw):
    buf = io.BytesIO()
    img.save(buf, format="PNG", **save_kw)
    return buf.getvalue()


def test_untagged_image_is_unchanged():
    arr = np.full((20, 20, 3), (200, 40, 60), dtype=np.uint8)
    out, meta = decode_image(png(Image.fromarray(arr)))
    assert meta["icc_converted"] is False
    assert np.array_equal(out, arr)


def test_srgb_tagged_image_stays_close():
    arr = np.full((20, 20, 3), (200, 40, 60), dtype=np.uint8)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    out, meta = decode_image(png(Image.fromarray(arr), icc_profile=icc))
    assert meta["icc_converted"] is True
    assert np.abs(out.astype(int) - arr.astype(int)).max() <= 1


def _s15(x):
    return struct.pack(">i", int(round(x * 65536)))


def display_p3_profile() -> bytes:
    """پروفایل ICC ماتریسی Display P3 (D50) — همون چیزی که آیفون توی عکس‌ها می‌ذاره."""
    xyz = lambda v: b"XYZ " + b"\0" * 4 + b"".join(_s15(c) for c in v)
    para = b"para" + b"\0" * 4 + struct.pack(">HH", 3, 0) + b"".join(
        _s15(v) for v in (2.4, 1 / 1.055, 0.055 / 1.055, 1 / 12.92, 0.04045))
    desc_ascii = b"Display P3 test\0"
    desc = (b"desc" + b"\0" * 4 + struct.pack(">I", len(desc_ascii)) + desc_ascii
            + struct.pack(">IIHB", 0, 0, 0, 0) + b"\0" * 67)
    text = b"text" + b"\0" * 4 + b"test\0"
    tags = {
        b"desc": desc, b"cprt": text,
        b"wtpt": xyz((0.9642, 1.0, 0.8249)),
        b"rXYZ": xyz((0.515121, 0.241196, -0.001053)),
        b"gXYZ": xyz((0.291977, 0.692245, 0.041886)),
        b"bXYZ": xyz((0.157105, 0.066559, 0.784073)),
        b"rTRC": para, b"gTRC": para, b"bTRC": para,
    }
    n = len(tags)
    offset = 128 + 4 + 12 * n
    table, body = b"", b""
    for sig, data in tags.items():
        pad = (-len(data)) % 4
        table += sig + struct.pack(">II", offset + len(body), len(data))
        body += data + b"\0" * pad
    size = offset + len(body)
    header = (struct.pack(">I", size) + b"\0" * 4 + struct.pack(">I", 0x02400000)
              + b"mntr" + b"RGB " + b"XYZ " + struct.pack(">6H", 2024, 1, 1, 0, 0, 0)
              + b"acsp" + b"\0" * 4 + b"\0" * 4 + b"\0" * 8 + b"\0" * 8
              + struct.pack(">I", 0) + _s15(0.9642) + _s15(1.0) + _s15(0.8249)
              + b"\0" * 4 + b"\0" * 44)
    assert len(header) == 128
    return header + struct.pack(">I", n) + table + body


def test_display_p3_image_is_converted_to_srgb():
    arr = np.full((20, 20, 3), (200, 40, 60), dtype=np.uint8)
    out, meta = decode_image(png(Image.fromarray(arr), icc_profile=display_p3_profile()))
    assert meta["icc_converted"] is True
    # همون اعداد توی گستره‌ی P3 رنگ «اشباع‌تر» ـن → توی sRGB قرمز بالاتر و سبز پایین‌تر
    assert out[0, 0, 0] > 200 and out[0, 0, 1] < 40
    # خاکستری خنثی خنثی می‌مونه
    gray, _ = decode_image(png(Image.fromarray(np.full((8, 8, 3), 128, np.uint8)), icc_profile=display_p3_profile()))
    assert np.abs(gray.astype(int) - 128).max() <= 2


def test_garbage_and_huge_images_raise_image_error(monkeypatch):
    with pytest.raises(ImageError):
        decode_image(b"nope")
    monkeypatch.setattr("app.imaging.MAX_PIXELS", 100)
    with pytest.raises(ImageError):
        decode_image(png(Image.new("RGB", (50, 50))))
