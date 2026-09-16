from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.seller import Seller
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="نشست معتبر نیست یا منقضی شده",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_error
    return user


def get_current_seller(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Seller:
    """
    فقط کاربرهایی که یه ردیف متناظر توی جدول seller دارن اجازه‌ی عبور دارن.
    یعنی مرز Supplier/Buyer دقیقاً همون چیزیه که قبلاً تصمیم گرفتیم:
    نه یه فیلد role روی users، بلکه وجود/عدم‌وجود ردیف توی seller.
    """
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این مسیر فقط برای فروشنده‌هاست — اول باید ثبت‌نام seller رو کامل کنی",
        )
    return seller
