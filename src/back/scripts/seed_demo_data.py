# -*- coding: utf-8 -*-
"""
اسکریپت Seed — برای پر کردن دیتابیس با داده‌ی اولیه‌ی لازم برای دموی لایو:
    ۱. ۶ تا skin_tone_anchor نهایی پروژه
    ۲. یه seller/brand/product نمونه
    ۳. چند تا shade نمونه با base_pigment_color واقعی + shade_render_profile
       محاسبه‌شده برای هر Anchor (دقیقاً با همون منطق color_engine که قبلاً تست شد)

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
from app.core.security import hash_password
from app.color_engine.blend import compute_all_render_profiles
from app.models.user import User
from app.models.seller import Seller
from app.models.brand import Brand
from app.models.product import Product
from app.models.shade import Shade
from app.models.skin_tone_anchor import SkinToneAnchor
from app.models.shade_render_profile import ShadeRenderProfile

# ---------- داده‌ی ثابت: ۶ Anchor نهایی پروژه ----------
SKIN_TONE_ANCHORS = [
    {"name": "روشن-خنثی",        "reference_color": "#F4DBC9", "sort_order": 1},
    {"name": "روشن-زیتونی",      "reference_color": "#E6DCB0", "sort_order": 2},
    {"name": "متوسط-خنثی",       "reference_color": "#D9B48A", "sort_order": 3},
    {"name": "متوسط-زیتونی",     "reference_color": "#C2B47E", "sort_order": 4},
    {"name": "گندمی‌تیره-خنثی",  "reference_color": "#9C7A52", "sort_order": 5},
    {"name": "گندمی‌تیره-زیتونی", "reference_color": "#9C8A5C", "sort_order": 6},
]

# ---------- داده‌ی نمونه: یه brand + چند shade واقع‌بینانه ----------
DEMO_SELLER = {
    "email": "demo-seller@example.com",
    "password": "demo-password-123",
    "full_name": "فروشنده‌ی نمونه",
    "business_name": "برند نمونه",
    "phone_number": "09120000000",
}

DEMO_BRAND = {"name": "کالکشن دمو", "description": "برند نمونه برای دموی لایو"}

DEMO_PRODUCT = {
    "name": "رژ لب مدادی دمو",
    "category": "lipstick",
    "description": "محصول نمونه برای نمایش قابلیت Try-On",
    "image_path": "products/demo-product.jpg",  # مسیر نمونه در MinIO (ماژول بعدی)
}

# رنگ‌های base_pigment_color دستی (چون هنوز عکس واقعی Swatch آپلود نشده،
# این‌ها مستقیم به‌عنوان رنگ پایه در نظر گرفته می‌شن، نه از extraction.py)
DEMO_SHADES = [
    {"name": "رز کلاسیک",  "finish": "matte",  "base_pigment_color": "#B0223A",
     "swatch_image_path": "swatches/demo-rose-classic.jpg"},
    {"name": "مرجانی",     "finish": "glossy", "base_pigment_color": "#E0645A",
     "swatch_image_path": "swatches/demo-coral.jpg"},
    {"name": "نودی گرم",   "finish": "matte",  "base_pigment_color": "#B97A62",
     "swatch_image_path": "swatches/demo-warm-nude.jpg"},
    {"name": "بروندی",     "finish": "glossy", "base_pigment_color": "#7A2E3B",
     "swatch_image_path": "swatches/demo-burgundy.jpg"},
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
    user = db.query(User).filter(User.email == DEMO_SELLER["email"]).first()
    if user is None:
        user = User(
            email=DEMO_SELLER["email"],
            password_hash=hash_password(DEMO_SELLER["password"]),
            full_name=DEMO_SELLER["full_name"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"  کاربر seller نمونه ساخته شد (id={user.id})")
    else:
        print(f"  کاربر seller نمونه از قبل بود (id={user.id})")

    seller = db.query(Seller).filter(Seller.user_id == user.id).first()
    if seller is None:
        seller = Seller(
            user_id=user.id,
            business_name=DEMO_SELLER["business_name"],
            phone_number=DEMO_SELLER["phone_number"],
        )
        db.add(seller)
        db.commit()
        db.refresh(seller)
        print(f"  ردیف seller ساخته شد (id={seller.id})")
    return seller


def seed_demo_brand_product(db, seller):
    brand = db.query(Brand).filter(Brand.seller_id == seller.id, Brand.name == DEMO_BRAND["name"]).first()
    if brand is None:
        brand = Brand(seller_id=seller.id, **DEMO_BRAND)
        db.add(brand)
        db.commit()
        db.refresh(brand)
        print(f"  برند نمونه ساخته شد (id={brand.id})")
    else:
        print(f"  برند نمونه از قبل بود (id={brand.id})")

    product = db.query(Product).filter(Product.brand_id == brand.id, Product.name == DEMO_PRODUCT["name"]).first()
    if product is None:
        product = Product(brand_id=brand.id, **DEMO_PRODUCT)
        db.add(product)
        db.commit()
        db.refresh(product)
        print(f"  محصول نمونه ساخته شد (id={product.id})")
    else:
        print(f"  محصول نمونه از قبل بود (id={product.id})")
    return product


def seed_demo_shades(db, product, anchors):
    anchors_payload = [{"id": a.id, "reference_color": a.reference_color} for a in anchors]

    for shade_data in DEMO_SHADES:
        existing = db.query(Shade).filter(
            Shade.product_id == product.id, Shade.name == shade_data["name"]
        ).first()
        if existing:
            print(f"  Shade «{shade_data['name']}» از قبل بود (id={existing.id}) — رد شد")
            continue

        shade = Shade(product_id=product.id, **shade_data)
        db.add(shade)
        db.commit()
        db.refresh(shade)

        profiles = compute_all_render_profiles(
            shade.base_pigment_color, shade.finish, anchors_payload
        )
        for p in profiles:
            db.add(ShadeRenderProfile(shade_id=shade.id, **p))
        db.commit()

        print(f"  Shade «{shade_data['name']}» ساخته شد (id={shade.id}) + {len(profiles)} render_profile")


def main():
    Base.metadata.create_all(bind=engine)  # فقط اگه جدول‌ها هنوز نساخته شدن
    db = SessionLocal()
    try:
        print("۱. Anchorهای پوستی...")
        anchors = seed_skin_tone_anchors(db)

        print("۲. Seller نمونه...")
        seller = seed_demo_seller(db)

        print("۳. Brand و Product نمونه...")
        product = seed_demo_brand_product(db, seller)

        print("۴. Shadeهای نمونه + render_profile...")
        seed_demo_shades(db, product, anchors)

        print("\nتموم شد.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
