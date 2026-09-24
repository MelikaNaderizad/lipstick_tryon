from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

# نوع محصول — سطح Product، نه Shade. یه برند می‌تونه چند نوع محصول داشته
# باشه (مثلاً مایع، جامد، لیپ‌گلاس، بالم، اویل، پلامپر)، و هر Product چند
# رنگ (Shade) مختلف داره.
PRODUCT_CATEGORIES = ("liquid", "stick", "gloss", "balm", "oil", "plumper")


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint(
            f"category IN {PRODUCT_CATEGORIES}", name="product_category_check"
        ),
    )

    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey("brand.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    image_path = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    brand = relationship("Brand", back_populates="products")
    shades = relationship("Shade", back_populates="product")
