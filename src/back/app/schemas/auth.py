from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime
    is_seller: bool

    class Config:
        from_attributes = True


class SellerRegisterRequest(BaseModel):
    business_name: str
    phone_number: str


class SellerResponse(BaseModel):
    id: int
    user_id: int
    business_name: str
    phone_number: str
    created_at: datetime

    class Config:
        from_attributes = True
