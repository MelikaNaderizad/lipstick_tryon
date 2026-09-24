from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models.shade import Shade
from app.models.skin_tone_anchor import SkinToneAnchor
from app.storage.backend import get_url

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/skin-tone-anchors")
def list_skin_tone_anchors(db: Session = Depends(get_db)):
    anchors = db.query(SkinToneAnchor).order_by(SkinToneAnchor.sort_order).all()
    return [
        {"id": a.id, "name": a.name, "reference_color": a.reference_color}
        for a in anchors
    ]


@router.get("/shades")
def list_demo_shades(include_all: bool = False, db: Session = Depends(get_db)):
    """
    برای دموی لایو — بدون Auth. پیش‌فرض فقط رنگ‌های «تأیید شده» (approved) برمی‌گرده
    تا تأیید/رد توی صفحه‌ی /review روی دمو اثر داشته باشه؛ با ?include_all=true همه.
    برای هر Shade، رنگ پایه + رنگ محاسبه‌شده روی هر Anchor (از shade_render_profile) هست.
    اگه عکس Swatch در ذخیره‌گاه موجود باشه، URL قابل‌نمایش هم اضافه می‌شه.
    """
    query = (
        db.query(Shade)
        .options(joinedload(Shade.product), selectinload(Shade.render_profiles))
        .order_by(Shade.id)
    )
    if not include_all:
        query = query.filter(Shade.status == "approved")

    return [
        {
            "id": shade.id,
            "name": shade.name,
            "product_id": shade.product_id,
            "product_name": shade.product.name,
            "product_type": shade.product.category,
            "base_pigment_color": shade.base_pigment_color,
            "status": shade.status,
            "swatch_image_url": get_url(shade.swatch_image_path),  # None اگه فایل نباشه — دمو بدون عکس هم کار می‌کنه
            "render_profiles": [
                {"skin_tone_anchor_id": p.skin_tone_anchor_id, "render_color": p.render_color}
                for p in shade.render_profiles
            ],
        }
        for shade in query.all()
    ]
