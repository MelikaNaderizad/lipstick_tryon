import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.seller import Seller

AUTH_MODE = os.getenv("AUTH_MODE", "dev")  # dev | jwt
HOST_JWT_SECRET = os.getenv("HOST_JWT_SECRET", "")
HOST_JWT_ALGORITHM = os.getenv("HOST_JWT_ALGORITHM", "HS256")


@dataclass
class Identity:
    external_user_id: str


def get_identity(
    authorization: str | None = Header(default=None),
    x_external_user_id: str | None = Header(default=None),
) -> Identity:
    if AUTH_MODE == "dev":
        # فقط برای توسعه؛ توی production نباید فعال باشه
        if not x_external_user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "هدر X-External-User-Id لازمه")
        return Identity(external_user_id=x_external_user_id)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن لازمه")
    try:
        payload = jwt.decode(authorization[7:], HOST_JWT_SECRET, algorithms=[HOST_JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن معتبر نیست")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن فیلد sub نداره")
    return Identity(external_user_id=str(sub))


def get_current_seller(
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
) -> Seller:
    seller = db.query(Seller).filter(Seller.external_user_id == identity.external_user_id).first()
    if seller is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "این مسیر فقط برای فروشنده‌هاست — اول باید به‌عنوان فروشنده ثبت بشی",
        )
    return seller