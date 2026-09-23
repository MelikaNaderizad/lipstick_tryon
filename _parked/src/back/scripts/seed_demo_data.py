# -*- coding: utf-8 -*-
"""
اسکریپت Seed — برای پر کردن دیتابیس با داده‌ی اولیه‌ی لازم برای دموی لایو:
    ۱. ۶ تا skin_tone_anchor نهایی پروژه
    ۲. یه seller/brand نمونه
    ۳. چند تا Product زیر همون Brand — هرکدوم یه «نوع» متفاوت (مایع/جامد/...)
    ۴. برای هر Product، چند Shade (رنگ) با base_pigment_color واقعی +
       shade_render_profile محاسبه‌شده برای هر Anchor
    ۵. آپلود عکس واقعی هر Shade از پوشه‌ی sample_swatches/ (اگه گذاشته باشی)

ساختار داده دقیقاً مطابق دنیای واقعیه: یه Brand چند Product (نوع) داره،
هر Product چند Shade (رنگ) داره. «نوع» سطح Product‌ه، نه Shade — قبلاً
finish (matte/glossy) روی Shade بود که حذف شده.

Idempotent: اجرای دوباره‌ش داده‌ی تکراری نمی‌سازه (بر اساس name/email چک می‌کنه).

اجرا:
    cd src/back
    DATABASE_URL=... python -m scripts.seed_demo_data
(اگه DATABASE_URL ندی، همون پیش‌فرض .env / database.py استفاده می‌شه)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401  (registers all models on Base.metadata)
from app.color_engine.blend import compute_all_render_profiles
from app.models.seller import Seller
from app.models.brand import Brand
from app.models.product import Product
from app.models.shade import Shade
from app.models.skin_tone_anchor import SkinToneAnchor
from app.models.shade_render_profile import ShadeRenderProfile
from app.storage.backend import upload_file, object_exists

# ---------- داده‌ی ثابت: ۶ Anchor نهایی پروژه ----------
SKIN_TONE_ANCHORS = [
    {"name": "روشن-خنثی",        "reference_color": "#F4DBC9", "sort_order": 1},
    {"name": "روشن-زیتونی",      "reference_color": "#E6DCB0", "sort_order": 2},
    {"name": "متوسط-خنثی",       "reference_color": "#D9B48A", "sort_order": 3},
    {"name": "متوسط-زیتونی",     "reference_color": "#C2B47E", "sort_order": 4},
    {"name": "گندمی‌تیره-خنثی",  "reference_color": "#9C7A52", "sort_order": 5},
    {"name": "گندمی‌تیره-زیتونی", "reference_color": "#9C8A5C", "sort_order": 6},
]

DEMO_SELLER = {
    "external_user_id": "demo-seller",
    "business_name": "برند نمونه",
    "phone_number": "09120000000",
}

DEMO_BRAND = {"name": "کالکشن دمو", "description": "برند نمونه برای دموی لایو"}

# عکس‌های واقعی سواچ رو خودت اینجا می‌ذاری — اسکریپت هیچی خودش نمی‌سازه.
# اسم فایل باید دقیقاً همون بخش آخر swatch_image_path باشه.
SAMPLE_SWATCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_swatches")

# ---------- داده‌ی نمونه: یه Brand با ۲ نوع محصول مختلف ----------
# category باید یکی از این‌ها باشه: liquid, stick, gloss, balm, oil, plumper
# رنگ‌های base_pigment_color دستی وارد شدن (نه از extraction.py) — طبق تصمیم
# فعلی، مرحله‌ی استخراج خودکار رنگ از عکس فعلاً کنار گذاشته شده.
DEMO_PRODUCTS = [
    {
        "category": "liquid",
        "name": "رژ لب مایع دمو",
        "description": "محصول نمونه از نوع مایع",
        "image_path": "products/demo-liquid.jpg",
        "shades": [
            {"name": "رز کلاسیک", "base_pigment_color": "#B0223A",
             "swatch_image_path": "swatches/demo-rose-classic.jpg"},
            {"name": "مرجانی", "base_pigment_color": "#E0645A",
             "swatch_image_path": "swatches/demo-coral.jpg"},
        ],
    },
    {
        "category": "stick",
        "name": "رژ لب جامد دمو",
        "description": "محصول نمونه از نوع جامد",
        "image_path": "products/demo-stick.jpg",
        "shades": [
            {"name": "نودی گرم", "base_pigment_color": "#B97A62",
             "swatch_image_path": "swatches/demo-warm-nude.jpg"},
            {"name": "بروندی", "base_pigment_color": "#7A2E3B",
             "swatch_image_path": "swatches/demo-burgundy.jpg"},
        ],
    },
]


def seed_skin_tone_anchors(db):
    created = 0
    for anchor_data in SKIN_TONE_ANCHORS:
        existing = db.query(SkinToneAnchor).filter(SkinToneAnchor.name == anchor_data["name"]).first()
        if existing:
            continue
        db.add(SkinToneAnchor(**anchor_data))
        created += 1
    db.commit()
    print(f"  Anchorهای پوستی: {created} تا جدید ساخته شد (بقیه از قبل بودن)")
    return db.query(SkinToneAnchor).order_by(SkinToneAnchor.sort_order).all()


def seed_demo_seller(db):
    seller = db.query(Seller).filter(
        Seller.external_user_id == DEMO_SELLER["external_user_id"]
    ).first()
    if seller is None:
        seller = Seller(**DEMO_SELLER)
        db.add(seller)
        db.commit()
        db.refresh(seller)
        print(f"  seller نمونه ساخته شد (id={seller.id})")
    else:
        print(f"  seller نمونه از قبل بود (id={seller.id})")
    return seller


def seed_demo_brand(db, seller):
    brand = db.query(Brand).filter(Brand.seller_id == seller.id, Brand.name == DEMO_BRAND["name"]).first()
    if brand is None:
        brand = Brand(seller_id=seller.id, **DEMO_BRAND)
        db.add(brand)
        db.commit()
        db.refresh(brand)
        print(f"  برند نمونه ساخته شد (id={brand.id})")
    else:
        print(f"  برند نمونه از قبل بود (id={brand.id})")
    return brand


def seed_demo_products_and_shades(db, brand, anchors):
    anchors_payload = [{"id": a.id, "reference_color": a.reference_color} for a in anchors]
    all_shades = []

    for product_data in DEMO_PRODUCTS:
        shades_data = product_data["shades"]
        product_fields = {k: v for k, v in product_data.items() if k != "shades"}

        product = db.query(Product).filter(
            Product.brand_id == brand.id, Product.name == product_fields["name"]
        ).first()
        if product is None:
            product = Product(brand_id=brand.id, **product_fields)
            db.add(product)
            db.commit()
            db.refresh(product)
            print(f"  Product «{product_fields['name']}» (نوع: {product_fields['category']}) ساخته شد (id={product.id})")
        else:
            print(f"  Product «{product_fields['name']}» از قبل بود (id={product.id})")

        for shade_data in shades_data:
            existing = db.query(Shade).filter(
                Shade.product_id == product.id, Shade.name == shade_data["name"]
            ).first()
            if existing:
                print(f"    Shade «{shade_data['name']}» از قبل بود (id={existing.id}) — رد شد")
                all_shades.append(existing)
                continue

            shade = Shade(product_id=product.id, **shade_data)
            db.add(shade)
            db.commit()
            db.refresh(shade)

            profiles = compute_all_render_profiles(shade.base_pigment_color, anchors_payload)
            for p in profiles:
                db.add(ShadeRenderProfile(shade_id=shade.id, **p))
            db.commit()

            print(f"    Shade «{shade_data['name']}» ساخته شد (id={shade.id}) + {len(profiles)} render_profile")
            all_shades.append(shade)

    return all_shades


def seed_shade_images(db, shades):
    """
    عکس Swatch رو خودمون نمی‌سازیم — فقط اگه خودت عکس واقعی رو با اسم درست
    توی پوشه‌ی scripts/sample_swatches/ گذاشته باشی، آپلودش می‌کنیم.
    اگه فایل نباشه، فقط هشدار می‌ده و رد می‌شه (کل Seed رو متوقف نمی‌کنه).
    """
    uploaded, skipped, missing, failed = 0, 0, 0, 0
    for shade in shades:
        if not shade.swatch_image_path:
            continue

        local_filename = os.path.basename(shade.swatch_image_path)
        local_path = os.path.join(SAMPLE_SWATCH_DIR, local_filename)

        try:
            if object_exists(shade.swatch_image_path):
                skipped += 1
                continue
        except Exception as exc:
            failed += 1
            print(f"    ⚠️  چک کردن «{shade.name}» توی MinIO ناموفق بود ({exc})")
            continue

        if not os.path.isfile(local_path):
            missing += 1
            print(f"    ⏭  عکس «{shade.name}» پیدا نشد — این فایل رو بذار: {local_path}")
            continue

        try:
            upload_file(local_path, shade.swatch_image_path)
            uploaded += 1
            print(f"    ✓ عکس «{shade.name}» آپلود شد ({local_filename})")
        except Exception as exc:
            failed += 1
            print(f"    ⚠️  آپلود عکس «{shade.name}» ناموفق بود ({exc}) — MinIO رو چک کن")

    print(f"  عکس‌ها: {uploaded} تا آپلود شد، {skipped} تا از قبل بود، "
          f"{missing} تا فایلش پیدا نشد، {failed} تا خطا داد")


def main():
    db = SessionLocal()
    try:
        print("۱. Anchorهای پوستی...")
        anchors = seed_skin_tone_anchors(db)

        print("۲. Seller نمونه...")
        seller = seed_demo_seller(db)

        print("۳. Brand نمونه...")
        brand = seed_demo_brand(db, seller)

        print("۴. Productها (انواع) و Shadeها (رنگ‌ها)...")
        shades = seed_demo_products_and_shades(db, brand, anchors)

        print("۵. عکس‌های Swatch (آپلود در MinIO)...")
        seed_shade_images(db, shades)

        print("\nتموم شد.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
