from sqlalchemy import Column, Integer, SmallInteger, String
from sqlalchemy.orm import relationship

from app.database import Base


class SkinToneAnchor(Base):
    __tablename__ = "skin_tone_anchor"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    reference_color = Column(String(7), nullable=False)
    sort_order = Column(SmallInteger, nullable=False, server_default="0")

    render_profiles = relationship("ShadeRenderProfile", back_populates="skin_tone_anchor")
    tryon_sessions = relationship("TryOnSession", back_populates="skin_tone_anchor")
