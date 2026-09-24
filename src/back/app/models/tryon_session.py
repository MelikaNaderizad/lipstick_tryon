from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class TryOnSession(Base):
    __tablename__ = "tryon_session"
    __table_args__ = (
        CheckConstraint(
            "skin_tone_source IN ('manual_override', 'auto_detected')",
            name="tryon_session_skin_tone_source_check",
        ),
    )

    id = Column(Integer, primary_key=True)
    external_user_id = Column(String, nullable=True)  # NULL = guest
    skin_tone_anchor_id = Column(Integer, ForeignKey("skin_tone_anchor.id"), nullable=False)
    shade_id = Column(Integer, ForeignKey("shade.id"), nullable=False)
    skin_tone_source = Column(String, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)

    skin_tone_anchor = relationship("SkinToneAnchor", back_populates="tryon_sessions")
    shade = relationship("Shade", back_populates="tryon_sessions")