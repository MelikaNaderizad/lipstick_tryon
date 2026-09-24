"""API مینیمال: /extract (با کادر خودِ کاربر: پوست + رژ) و ذخیره‌ی نتیجه‌ها."""
import io

import numpy as np
from PIL import Image, ImageDraw

from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab

SKIN_BOX = "0.05,0.05,0.45,0.45"
SWATCH_BOX = "0.55,0.55,0.95,0.95"


def de(a, b):
    return delta_e_76(rgb255_to_lab(hex_to_rgb255(a)), rgb255_to_lab(hex_to_rgb255(b)))


def make_image(pigment=(176, 34, 58), skin=(238, 200, 175), distractor=None, w=400, h=400, seed=0):
    """
    عکس با پوست بالا-چپ، رژ پایین-راست (دقیقاً همون جایی که SKIN_BOX/SWATCH_BOX
    اشاره می‌کنن)، و یه distractor اختیاری (مثلاً آستین قرمز) جای دیگه‌ی فریم که
    نباید روی نتیجه اثر بذاره.
    """
    arr = np.zeros((h, w, 3), dtype=np.float64)
    arr[:, :] = np.array(skin)
    rng = np.random.default_rng(seed)
    arr = np.clip(arr + rng.normal(0, 2, arr.shape), 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    draw.rectangle([int(0.55 * w), int(0.55 * h), int(0.95 * w) - 1, int(0.95 * h) - 1], fill=pigment)
    if distractor:
        draw.rectangle([0, int(0.7 * h), int(0.2 * w), h - 1], fill=distractor)  # پایین-چپ، بیرون هر دو کادر
    return np.array(img)


def jpeg_bytes(arr, fmt="JPEG"):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format=fmt, quality=92)
    return buf.getvalue()


def post(client, arr=None, **data):
    arr = make_image() if arr is None else arr
    data.setdefault("skin_box", SKIN_BOX)
    data.setdefault("swatch_box", SWATCH_BOX)
    data.setdefault("correction_mode", "none")
    return client.post("/extract", data=data, files={"swatch": ("s.jpg", jpeg_bytes(arr), "image/jpeg")})


def test_health_and_index(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] in ("ok", "error")  # بسته به بالا بودن Postgres
    page = client.get("/")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    page = client.get("/review")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    anchors = client.get("/anchors").json()
    assert len(anchors) == 6


def test_extract_reads_only_inside_swatch_box(client):
    r = post(client, name="Rose", expected_color="#B0223A")
    assert r.status_code == 200, r.text
    body = r.json()
    assert de("#B0223A", body["base_pigment_color"]) < 4
    assert body["delta_e"] < 4

    listed = client.get("/extractions").json()
    assert [x["id"] for x in listed] == [body["id"]]
    img = client.get(body["image_url"])
    assert img.status_code == 200 and img.headers["content-type"].startswith("image/")


def test_distractor_outside_boxes_is_ignored(client):
    """یه مستطیل قرمز پررنگ (شبیه آستین) بیرون کادرها نباید رنگ استخراجی رو عوض کنه."""
    clean = make_image(pigment=(190, 150, 130))  # رژ نودی کم‌کروما
    with_sleeve = make_image(pigment=(190, 150, 130), distractor=(220, 20, 20))
    c1 = post(client, clean, save="false").json()["base_pigment_color"]
    c2 = post(client, with_sleeve, save="false").json()["base_pigment_color"]
    assert de(c1, c2) < 2


def test_missing_boxes_is_422(client):
    arr = make_image()
    r = client.post("/extract", data={"correction_mode": "none"}, files={"swatch": ("s.jpg", jpeg_bytes(arr), "image/jpeg")})
    assert r.status_code == 422
    r = client.post("/extract", data={"skin_box": SKIN_BOX, "correction_mode": "none"},
                    files={"swatch": ("s.jpg", jpeg_bytes(arr), "image/jpeg")})
    assert r.status_code == 422


def test_selected_anchor_with_exposure_correction(client):
    dim = make_image(pigment=(176, 34, 58), skin=(150, 120, 100))  # پوست تیره‌تر شبیه‌سازی‌شده
    r = post(client, dim, correction_mode="exposure", anchor_id="1", expected_color="#B0223A")
    assert r.status_code == 200
    assert r.json()["extraction"]["correction_source"].startswith("selected_anchor")


def test_save_false_does_not_store(client):
    r = post(client, save="false")
    assert r.status_code == 200 and r.json()["id"] is None
    assert client.get("/extractions").json() == []


def test_delete(client):
    rid = post(client).json()["id"]
    assert client.delete(f"/extractions/{rid}").status_code == 204
    assert client.get(f"/extractions/{rid}").status_code == 404
    assert client.delete(f"/extractions/{rid}").status_code == 404


def test_bad_inputs(client):
    arr = make_image()
    r = client.post("/extract", data={"skin_box": SKIN_BOX, "swatch_box": SWATCH_BOX},
                    files={"swatch": ("s.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 415
    r = client.post("/extract", data={"skin_box": SKIN_BOX, "swatch_box": SWATCH_BOX},
                    files={"swatch": ("s.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400
    assert post(client, swatch_box="0.9,0.9,0.1,0.1").status_code == 422
    assert post(client, anchor_id="999").status_code == 422
    assert post(client, correction_mode="bogus").status_code == 422
    assert post(client, expected_color="red").status_code == 422


def test_apply_without_face_returns_422_or_503(client):
    arr = make_image()
    r = client.post("/apply", data={"color": "#B0223A"},
                    files={"photo": ("p.jpg", jpeg_bytes(arr), "image/jpeg")})
    assert r.status_code in (422, 503)


def test_apply_bad_color(client):
    arr = make_image()
    r = client.post("/apply", data={"color": "red"},
                    files={"photo": ("p.jpg", jpeg_bytes(arr), "image/jpeg")})
    assert r.status_code == 422
