from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Taxpayer(Base):
    __tablename__ = "taxpayers"

    id = Column(Integer, primary_key=True, index=True)

    taxpayer_reference = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name = Column(
        String(200),
        nullable=False,
    )

    phone_number = Column(
        String(30),
        nullable=False,
        index=True,
    )

    whatsapp_number = Column(
        String(30),
        nullable=True,
        index=True,
    )

    email = Column(
        String(255),
        nullable=True,
        index=True,
    )

    occupation = Column(
        String(200),
        nullable=True,
    )

    address = Column(
        String(500),
        nullable=True,
    )

    city = Column(
        String(100),
        nullable=True,
    )

    state = Column(
        String(100),
        nullable=False,
        default="Edo",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    conversations = relationship(
        "Conversation",
        back_populates="taxpayer",
        cascade="all, delete-orphan",
    )