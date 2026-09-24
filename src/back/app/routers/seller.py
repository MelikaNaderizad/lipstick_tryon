import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import Identity, get_current_seller, get_identity
from app.color_engine.blend import compute_all_render_profiles
from app.color_engine.extraction import extract_base_pigment_color
from app.color_engine.swatch_template import (
    DEFAULT_SKIN_BOX,
    DEFAULT_SWATCH_BOX,
    parse_box,
    to_pixels,
)
from app.database import get_db
from app.models.brand import Brand
from app.models.product import PRODUCT_CATEGORIES, Product
from app.models.seller import Seller
from app.models.shade import Shade
from app.models.shade_render_profile import ShadeRenderProfile
from app.models.skin_tone_anchor import SkinToneAnchor
from app.storage.backend import get_url, upload_bytes
from app.uploads import HEX_RE, read_upload

router = APIRouter(prefix="/seller", tags=["seller"])


# ------------------------------------------------------------------ seller
class SellerRegisterRequest(BaseModel):
    business_name: str
    phone_number: str | None = None


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_seller(
    payload: SellerRegisterRequest,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    """تبدیل یه کاربر سایت میزبان به seller (ساختن ردیف توی جدول seller)."""
    existing = db.query(Seller).filter(Seller.external_user_id == identity.external_user_id).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کاربر قبلاً seller شده")

    seller = Seller(
        external_user_id=identity.external_user_id,
        business_name=payload.business_name,
        phone_number=payload.phone_number,
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return {"id": seller.id, "business_name": seller.business_name}


@router.get("/ping")
def seller_ping(current_seller: Seller = Depends(get_current_seller)):
    return {"message": "دسترسی seller تأیید شد.", "seller_id": current_seller.id}


# ------------------------------------------------------------------ brand
class BrandCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


@router.post("/brands", status_code=status.HTTP_201_CREATED)
def create_brand(
    payload: BrandCreate,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    brand = Brand(seller_id=seller.id, name=payload.name, description=payload.description)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return {"id": brand.id, "name": brand.name, "description": brand.description}


@router.get("/brands")
def list_my_brands(seller: Seller = Depends(get_current_seller), db: Session = Depends(get_db)):
    brands = db.query(Brand).filter(Brand.seller_id == seller.id).order_by(Brand.id).all()
    return [{"id": b.id, "name": b.name, "description": b.description} for b in brands]


def _get_owned_brand(db, seller, brand_id) -> Brand:
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.seller_id == seller.id).first()
    if brand is None:
        # عمداً ۴۰۴ (نه ۴۰۳) تا وجود/عدم‌وجود برند دیگران لو نره
        raise HTTPException(status.HTTP_404_NOT_FOUND, "برند پیدا نشد")
    return brand


# ------------------------------------------------------------------ product
class ProductCreate(BaseModel):
    name: str = Field(min_length=1)
    category: str
    description: str = ""


@router.post("/brands/{brand_id}/products", status_code=status.HTTP_201_CREATED)
def create_product(
    brand_id: int,
    payload: ProductCreate,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    brand = _get_owned_brand(db, seller, brand_id)
    if payload.category not in PRODUCT_CATEGORIES:
        raise HTTPException(422, f"category باید یکی از {list(PRODUCT_CATEGORIES)} باشه")
    product = Product(
        brand_id=brand.id,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        image_path="",  # آپلود عکس محصول بعداً اضافه می‌شه
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"id": product.id, "brand_id": brand.id, "name": product.name, "category": product.category}


@router.get("/brands/{brand_id}/products")
def list_products(
    brand_id: int,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    brand = _get_owned_brand(db, seller, brand_id)
    products = db.query(Product).filter(Product.brand_id == brand.id).order_by(Product.id).all()
    return [{"id": p.id, "name": p.name, "category": p.category} for p in products]


def _get_owned_product(db, seller, product_id) -> Product:
    product = (
        db.query(Product)
        .join(Brand, Product.brand_id == Brand.id)
        .filter(Product.id == product_id, Brand.seller_id == seller.id)
        .first()
    )
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محصول پیدا نشد")
    return product


def _get_owned_shade(db, seller, shade_id) -> Shade:
    shade = (
        db.query(Shade)
        .join(Product, Shade.product_id == Product.id)
        .join(Brand, Product.brand_id == Brand.id)
        .filter(Shade.id == shade_id, Brand.seller_id == seller.id)
        .first()
    )
    if shade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "shade پیدا نشد")
    return shade


# ------------------------------------------------------------------ shade
def _shade_dict(shade: Shade, include_meta=True):
    d = {
        "id": shade.id,
        "product_id": shade.product_id,
        "name": shade.name,
        "base_pigment_color": shade.base_pigment_color,
        "color_source": shade.color_source,
        "swatch_image_path": shade.swatch_image_path,
        "swatch_image_url": get_url(shade.swatch_image_path),
        "status": shade.status,
        "render_profile_count": len(shade.render_profiles),
    }
    if include_meta:
        d["extraction_meta"] = shade.extraction_meta
    return d


def _box_or_default(text, default, field):
    if text is None or text == "":
        return default
    try:
        return parse_box(text)
    except ValueError as exc:
        raise HTTPException(422, f"{field}: {exc}")


def _add_render_profiles(db, shade, anchors):
    """render_color این shade روی هر Anchor رو حساب می‌کنه و به session اضافه می‌کنه (commit با صدا زننده‌ست)."""
    payload = [{"id": a.id, "reference_color": a.reference_color} for a in anchors]
    for p in compute_all_render_profiles(shade.base_pigment_color, payload):
        db.add(ShadeRenderProfile(shade_id=shade.id, **p))


# sync (def) عمداً: استخراج رنگ (GrabCut) و DB/MinIO همه blocking هستن؛ FastAPI اجراشون
# می‌کنه توی threadpool تا یه آپلود کل سرور رو قفل نکنه.
@router.post("/products/{product_id}/shades", status_code=status.HTTP_201_CREATED)
def create_shade_from_swatch(
    product_id: int,
    name: str = Form(...),
    swatch: UploadFile = File(...),
    skin_tone_anchor_id: int | None = Form(None),
    skin_box: str | None = Form(None),
    swatch_box: str | None = Form(None),
    gray_box: str | None = Form(None),
    correction_mode: str = Form("exposure"),
    manual_color: str | None = Form(None),
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    """
    آپلود عکس سواچ → ذخیره در MinIO → استخراج رنگ خالص → ساختن Shade
    (+ render_profile برای هر Anchor). اگه manual_color بدی، استخراج دور زده می‌شه.
    """
    product = _get_owned_product(db, seller, product_id)

    if correction_mode not in ("exposure", "full", "none"):
        raise HTTPException(422, "correction_mode نامعتبره")
    if manual_color and not HEX_RE.match(manual_color):
        raise HTTPException(422, "manual_color باید #RRGGBB باشه")

    raw, image, img_meta, ext = read_upload(swatch)

    anchors = db.query(SkinToneAnchor).order_by(SkinToneAnchor.sort_order).all()
    target_anchor_hex = None
    if skin_tone_anchor_id is not None:
        chosen = next((a for a in anchors if a.id == skin_tone_anchor_id), None)
        if chosen is None:
            raise HTTPException(422, "skin_tone_anchor_id نامعتبره")
        target_anchor_hex = chosen.reference_color

    if manual_color:
        color_hex = manual_color.upper()
        color_source = "manual"
        meta = {"note": "رنگ دستی وارد شده؛ استخراج انجام نشد"}
    else:
        h, w = image.shape[:2]
        skin_frac = _box_or_default(skin_box, DEFAULT_SKIN_BOX, "skin_box")
        swatch_frac = _box_or_default(swatch_box, DEFAULT_SWATCH_BOX, "swatch_box")
        gray_frac = _box_or_default(gray_box, None, "gray_box")
        try:
            result = extract_base_pigment_color(
                image,
                to_pixels(skin_frac, w, h),
                to_pixels(swatch_frac, w, h),
                gray_box=to_pixels(gray_frac, w, h) if gray_frac else None,
                skin_tone_anchors=[a.reference_color for a in anchors],
                target_anchor_hex=target_anchor_hex,
                correction_mode=correction_mode,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        color_hex = result["base_pigment_color"]
        color_source = "extracted"
        meta = {
            **result,
            "boxes_fraction": {"skin": skin_frac, "swatch": swatch_frac, "gray": gray_frac},
            "selected_anchor_id": skin_tone_anchor_id,
            "correction_mode": correction_mode,
            "icc_converted": img_meta["icc_converted"],
        }

    object_name = f"swatches/{seller.id}/{uuid.uuid4().hex}.{ext}"
    try:
        upload_bytes(raw, object_name, content_type=swatch.content_type)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"آپلود در MinIO ناموفق بود: {exc}")

    # shade و render_profileهاش توی یک تراکنش: یا هر دو ساخته می‌شن یا هیچ‌کدوم
    shade = Shade(
        product_id=product.id,
        name=name,
        base_pigment_color=color_hex,
        swatch_image_path=object_name,
        color_source=color_source,
        extraction_meta=meta,
    )
    db.add(shade)
    db.flush()  # id رو می‌گیره بدون commit
    _add_render_profiles(db, shade, anchors)
    db.commit()
    db.refresh(shade)

    return _shade_dict(shade)


@router.get("/products/{product_id}/shades")
def list_shades(
    product_id: int,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    product = _get_owned_product(db, seller, product_id)
    shades = db.query(Shade).filter(Shade.product_id == product.id).order_by(Shade.id).all()
    return [_shade_dict(s) for s in shades]


@router.get("/shades/{shade_id}")
def get_shade(
    shade_id: int,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    return _shade_dict(_get_owned_shade(db, seller, shade_id))


class ColorOverride(BaseModel):
    color: str


@router.patch("/shades/{shade_id}/color")
def override_shade_color(
    shade_id: int,
    payload: ColorOverride,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    """اصلاح دستی رنگ بعد از دیدن پیش‌نمایش («می‌تونید قبل از تأیید نهایی کمی اصلاحش کنید»)."""
    if not HEX_RE.match(payload.color):
        raise HTTPException(422, "color باید #RRGGBB باشه")
    shade = _get_owned_shade(db, seller, shade_id)
    shade.base_pigment_color = payload.color.upper()
    shade.color_source = "manual"

    anchors = db.query(SkinToneAnchor).order_by(SkinToneAnchor.sort_order).all()
    db.query(ShadeRenderProfile).filter(ShadeRenderProfile.shade_id == shade.id).delete()
    _add_render_profiles(db, shade, anchors)
    db.commit()
    db.refresh(shade)
    return _shade_dict(shade)


# ------------------------------------------------------------------ review
class StatusUpdate(BaseModel):
    status: str


@router.post("/shades/{shade_id}/status")
def set_shade_status(
    shade_id: int,
    payload: StatusUpdate,
    seller: Seller = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    """تأیید / رد / برگرداندن به «در انتظار» — فقط رنگ‌های approved توی /demo/shades دیده می‌شن."""
    if payload.status not in ("pending", "approved", "rejected"):
        raise HTTPException(422, "status باید pending یا approved یا rejected باشه")
    shade = _get_owned_shade(db, seller, shade_id)
    shade.status = payload.status
    db.commit()
    db.refresh(shade)
    return _shade_dict(shade)


@router.get("/overview")
def overview(seller: Seller = Depends(get_current_seller), db: Session = Depends(get_db)):
    """برندها → محصولات → تعداد shade و وضعیت‌ها (برای صفحه‌ی بررسی)."""
    out = []
    for b in db.query(Brand).filter(Brand.seller_id == seller.id).order_by(Brand.id).all():
        products = []
        for p in db.query(Product).filter(Product.brand_id == b.id).order_by(Product.id).all():
            shades = db.query(Shade).filter(Shade.product_id == p.id).all()
            products.append({
                "id": p.id, "name": p.name, "category": p.category,
                "shade_count": len(shades),
                "approved_count": sum(1 for s in shades if s.status == "approved"),
            })
        out.append({"id": b.id, "name": b.name, "products": products})
    return out
