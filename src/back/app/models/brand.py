from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Brand(Base):
    __tablename__ = "brand"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("seller.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    seller = relationship("Seller", back_populates="brands")
    products = relationship("Product", back_populates="brand")
