from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Seller(Base):
    __tablename__ = "seller"

    id = Column(Integer, primary_key=True)
    external_user_id = Column(String, unique=True, nullable=False, index=True)
    business_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    brands = relationship("Brand", back_populates="seller") 