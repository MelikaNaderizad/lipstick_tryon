from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Product(Base):
    __tablename__ = "product"

    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey("brand.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, server_default="lipstick")
    description = Column(Text, nullable=False)
    image_path = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    brand = relationship("Brand", back_populates="products")
    shades = relationship("Shade", back_populates="product")
