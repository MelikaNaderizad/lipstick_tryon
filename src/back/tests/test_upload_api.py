"""جریان کامل seller → برند → محصول → آپلود سواچ، با SQLite و MinIO جعلی."""
import io

import numpy as np
from PIL import Image

from app.color_engine.colorspace import delta_e_76, hex_to_rgb255, rgb255_to_lab
from scripts.make_test_swatches import make_swatch_image
from tests.conftest import as_user


def jpeg_bytes(img_arr, fmt="JPEG"):
    buf = io.BytesIO()
    Image.fromarray(img_arr).save(buf, format=fmt, quality=95)
    return buf.getvalue()


def de(a, b):
    return delta_e_76(rgb255_to_lab(hex_to_rgb255(a)), rgb255_to_lab(hex_to_rgb255(b)))


def setup_product(client, user="u1", category="liquid"):
    h = as_user(user)
    assert client.post("/seller/register", json={"business_name": "B"}, headers=h).status_code == 201
    brand = client.post("/seller/brands", json={"name": "Brand"}, headers=h).json()
    prod = client.post(f"/seller/brands/{brand['id']}/products",
                       json={"name": "P", "category": category}, headers=h)
    assert prod.status_code == 201
    return h, brand["id"], prod.json()["id"]


def upload(client, h, product_id, img, name="Shade", **data):
    return client.post(
        f"/seller/products/{product_id}/shades",
        headers=h, data={"name": name, **data},
        files={"swatch": ("s.jpg", jpeg_bytes(img), "image/jpeg")},
    )


def test_non_seller_is_forbidden(client):
    r = client.get("/seller/ping", headers=as_user("nobody"))
    assert r.status_code == 403


def test_missing_identity_header_is_401(client):
    assert client.get("/seller/ping").status_code == 401


def test_upload_extracts_color_and_creates_render_profiles(client, storage):
    h, _, pid = setup_product(client)
    img = make_swatch_image("#F4DBC9", "#B0223A", "neutral")
    r = upload(client, h, pid, img, name="Rose")
    assert r.status_code == 201, r.text
    shade = r.json()
    assert de("#B0223A", shade["base_pigment_color"]) < 6
    assert shade["color_source"] == "extracted"
    assert shade["render_profile_count"] == 6
    assert shade["pigment_alpha"] == 0.90  # alpha نوع liquid
    assert shade["swatch_image_path"] in storage  # عکس واقعاً آپلود شده
    assert "illuminant_gain" in shade["extraction_meta"]

    # همون شِید از دید دموی لایو هم دیده می‌شه
    listed = client.get("/demo/shades").json()
    assert any(s["id"] == shade["id"] and len(s["render_profiles"]) == 6 for s in listed)


def test_selected_anchor_is_used_and_recorded(client):
    h, _, pid = setup_product(client)
    anchors = client.get("/demo/skin-tone-anchors").json()
    light = next(a for a in anchors if a["reference_color"] == "#F4DBC9")
    img = make_swatch_image("#F4DBC9", "#B0223A", "dim")
    r = upload(client, h, pid, img, skin_tone_anchor_id=str(light["id"]))
    assert r.status_code == 201
    meta = r.json()["extraction_meta"]
    assert meta["selected_anchor_id"] == light["id"]
    assert meta["correction_source"].startswith("selected_anchor")
    assert de("#B0223A", r.json()["base_pigment_color"]) < 4


def test_manual_color_skips_extraction(client):
    h, _, pid = setup_product(client)
    img = make_swatch_image("#F4DBC9", "#B0223A")
    r = upload(client, h, pid, img, manual_color="#112233")
    assert r.status_code == 201
    assert r.json()["base_pigment_color"] == "#112233"
    assert r.json()["color_source"] == "manual"


def test_color_override_recomputes_render_profiles(client):
    h, _, pid = setup_product(client)
    shade = upload(client, h, pid, make_swatch_image("#F4DBC9", "#B0223A")).json()
    r = client.patch(f"/seller/shades/{shade['id']}/color", json={"color": "#00ff00"}, headers=h)
    assert r.status_code == 200
    assert r.json()["base_pigment_color"] == "#00FF00"
    demo = {s["id"]: s for s in client.get("/demo/shades").json()}[shade["id"]]
    assert len(demo["render_profiles"]) == 6
    assert client.patch(f"/seller/shades/{shade['id']}/color", json={"color": "red"}, headers=h).status_code == 422


def test_other_seller_cannot_touch_my_data(client):
    h1, brand_id, pid = setup_product(client, "u1")
    client.post("/seller/register", json={"business_name": "Other"}, headers=as_user("u2"))
    h2 = as_user("u2")
    img = make_swatch_image("#F4DBC9", "#B0223A")
    assert upload(client, h2, pid, img).status_code == 404
    assert client.get(f"/seller/brands/{brand_id}/products", headers=h2).status_code == 404
    shade = upload(client, h1, pid, img).json()
    assert client.get(f"/seller/shades/{shade['id']}", headers=h2).status_code == 404
    assert client.patch(f"/seller/shades/{shade['id']}/color", json={"color": "#000000"}, headers=h2).status_code == 404


def test_bad_inputs(client):
    h, _, pid = setup_product(client)
    img = make_swatch_image("#F4DBC9", "#B0223A")
    # فایل تصویر نیست
    r = client.post(f"/seller/products/{pid}/shades", headers=h, data={"name": "x"},
                    files={"swatch": ("s.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 400
    # نوع فایل غیرمجاز
    r = client.post(f"/seller/products/{pid}/shades", headers=h, data={"name": "x"},
                    files={"swatch": ("s.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 415
    # کادر نامعتبر
    assert upload(client, h, pid, img, swatch_box="0.9,0.9,0.1,0.1").status_code == 422
    # Anchor ناموجود
    assert upload(client, h, pid, img, skin_tone_anchor_id="999").status_code == 422
    # category نامعتبر
    brand = client.get("/seller/brands", headers=h).json()[0]
    assert client.post(f"/seller/brands/{brand['id']}/products",
                       json={"name": "P", "category": "matte"}, headers=h).status_code == 422


def test_storage_failure_returns_503_and_creates_no_shade(client, monkeypatch):
    h, _, pid = setup_product(client)

    def boom(*a, **k):
        raise RuntimeError("minio down")

    monkeypatch.setattr("app.routers.seller.upload_bytes", boom)
    r = upload(client, h, pid, make_swatch_image("#F4DBC9", "#B0223A"))
    assert r.status_code == 503
    assert client.get(f"/seller/products/{pid}/shades", headers=h).json() == []


def test_review_page_and_real_local_storage(real_storage_client):
    """صفحه‌ی بررسی سرو می‌شه و عکس آپلودشده واقعاً از /files قابل‌دریافته."""
    client = real_storage_client
    page = client.get("/review")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]

    h, _, pid = setup_product(client)
    shade = upload(client, h, pid, make_swatch_image("#F4DBC9", "#B0223A")).json()
    assert shade["swatch_image_url"].startswith("/files/swatches/")
    img = client.get(shade["swatch_image_url"])
    assert img.status_code == 200 and img.headers["content-type"].startswith("image/")
    assert Image.open(io.BytesIO(img.content)).size == (800, 600)


def test_status_workflow_and_overview(client):
    h, _, pid = setup_product(client)
    s1 = upload(client, h, pid, make_swatch_image("#F4DBC9", "#B0223A"), name="A").json()
    upload(client, h, pid, make_swatch_image("#F4DBC9", "#E0645A"), name="B")
    assert s1["status"] == "pending"

    r = client.post(f"/seller/shades/{s1['id']}/status", json={"status": "approved"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert client.post(f"/seller/shades/{s1['id']}/status", json={"status": "maybe"}, headers=h).status_code == 422
    # seller دیگه نمی‌تونه وضعیت رو عوض کنه
    client.post("/seller/register", json={"business_name": "X"}, headers=as_user("u2"))
    assert client.post(f"/seller/shades/{s1['id']}/status", json={"status": "rejected"},
                       headers=as_user("u2")).status_code == 404

    ov = client.get("/seller/overview", headers=h).json()
    prod = ov[0]["products"][0]
    assert prod["shade_count"] == 2 and prod["approved_count"] == 1
    listed = client.get(f"/seller/products/{pid}/shades", headers=h).json()
    assert {s["name"]: s["status"] for s in listed} == {"A": "approved", "B": "pending"}
    assert "extraction_meta" in listed[0]  # صفحه‌ی بررسی به boxes_fraction نیاز داره
