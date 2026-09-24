from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Shade(Base):
    __tablename__ = "shade"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="shade_status_check",
        ),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    name = Column(String, nullable=False)
    base_pigment_color = Column(String(7), nullable=False)
    swatch_image_path = Column(Text, nullable=False)
    color_source = Column(String, nullable=False, server_default="manual")  # manual | extracted
    extraction_meta = Column(JSON, nullable=True)
    status = Column(String, nullable=False, server_default="pending")  # pending | approved | rejected
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product", back_populates="shades")
    render_profiles = relationship("ShadeRenderProfile", back_populates="shade")
    tryon_sessions = relationship("TryOnSession", back_populates="shade")
