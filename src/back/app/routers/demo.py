from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.shade import Shade
from app.models.shade_render_profile import ShadeRenderProfile
from app.models.skin_tone_anchor import SkinToneAnchor
from app.storage.minio_client import get_presigned_url, object_exists

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/skin-tone-anchors")
def list_skin_tone_anchors(db: Session = Depends(get_db)):
    anchors = db.query(SkinToneAnchor).order_by(SkinToneAnchor.sort_order).all()
    return [
        {"id": a.id, "name": a.name, "reference_color": a.reference_color}
        for a in anchors
    ]


@router.get("/shades")
def list_demo_shades(db: Session = Depends(get_db)):
    """
    برای دموی لایو — بدون Auth. برای هر Shade، رنگ پایه + رنگ محاسبه‌شده روی
    هر Anchor رو برمی‌گردونه (از shade_render_profile، نه محاسبه‌ی لحظه‌ای).
    اگه عکس Swatch واقعاً در MinIO موجود باشه، URL موقت (presigned) هم اضافه می‌شه.
    """
    shades = db.query(Shade).all()
    result = []
    for shade in shades:
        profiles = (
            db.query(ShadeRenderProfile)
            .filter(ShadeRenderProfile.shade_id == shade.id)
            .all()
        )
        swatch_url = None
        if shade.swatch_image_path:
            try:
                if object_exists(shade.swatch_image_path):
                    swatch_url = get_presigned_url(shade.swatch_image_path)
            except Exception:
                # MinIO شاید هنوز بالا نیومده یا عکس واقعی آپلود نشده —
                # دمو باید بدون عکس هم کار کنه، فقط با رنگ.
                swatch_url = None

        result.append(
            {
                "id": shade.id,
                "name": shade.name,
                "finish": shade.finish,
                "base_pigment_color": shade.base_pigment_color,
                "swatch_image_url": swatch_url,
                "render_profiles": [
                    {
                        "skin_tone_anchor_id": p.skin_tone_anchor_id,
                        "render_color": p.render_color,
                    }
                    for p in profiles
                ],
            }
        )
    return result
