from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.seller import Seller
from app.models.user import User
from app.schemas.auth import (
    SellerRegisterRequest,
    SellerResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_response(user: User, db: Session) -> UserResponse:
    is_seller = db.query(Seller).filter(Seller.user_id == user.id).first() is not None
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
        is_seller=is_seller,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این ایمیل قبلاً ثبت‌نام کرده",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    invalid_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ایمیل یا رمز عبور اشتباهه",
    )
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise invalid_error

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_user_response(current_user, db)


@router.post("/become-seller", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
def become_seller(
    payload: SellerRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    تبدیل یه user لاگین‌کرده به seller — دقیقاً با ساختن یه ردیف توی جدول seller.
    هیچ فیلد role ای جایی تغییر نمی‌کنه، چون مرز Supplier/Buyer با وجود همین ردیفه.
    """
    existing = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این کاربر قبلاً seller شده",
        )

    seller = Seller(
        user_id=current_user.id,
        business_name=payload.business_name,
        phone_number=payload.phone_number,
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller
