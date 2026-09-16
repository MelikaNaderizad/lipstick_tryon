from fastapi import APIRouter, Depends

from app.api.deps import get_current_seller
from app.models.seller import Seller

router = APIRouter(prefix="/seller", tags=["seller"])


@router.get("/ping")
def seller_ping(current_seller: Seller = Depends(get_current_seller)):
    """
    یه Endpoint نمونه فقط برای اثبات این‌که مسیرهای seller درست محافظت می‌شن.
    CRUD واقعی برند/محصول/Shade توی فاز ۳ اینجا اضافه می‌شه.
    """
    return {
        "message": f"سلام {current_seller.business_name}، دسترسی seller تأیید شد.",
        "seller_id": current_seller.id,
    }
