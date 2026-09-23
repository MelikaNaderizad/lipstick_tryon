from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ShadeRenderProfile(Base):
    __tablename__ = "shade_render_profile"
    __table_args__ = (
        UniqueConstraint("shade_id", "skin_tone_anchor_id", name="uq_shade_anchor"),
    )

    id = Column(Integer, primary_key=True)
    shade_id = Column(Integer, ForeignKey("shade.id"), nullable=False)
    skin_tone_anchor_id = Column(Integer, ForeignKey("skin_tone_anchor.id"), nullable=False)
    render_color = Column(String(7), nullable=False)
    computed_at = Column(DateTime, server_default=func.now())

    shade = relationship("Shade", back_populates="render_profiles")
    skin_tone_anchor = relationship("SkinToneAnchor", back_populates="render_profiles")
