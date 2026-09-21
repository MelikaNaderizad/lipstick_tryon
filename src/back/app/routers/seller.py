from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import Identity, get_current_seller, get_identity
from app.database import get_db
from app.models.seller import Seller

router = APIRouter(prefix="/seller", tags=["seller"])


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