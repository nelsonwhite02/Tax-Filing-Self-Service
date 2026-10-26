
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class BusinessRegister(Base):
    __tablename__ = "business_register"

    id = Column(Integer, primary_key=True, index=True)

    business_name = Column(String(250), nullable=False, index=True)
    normalized_name = Column(String(250), nullable=False, index=True)

    registration_number = Column(String(100), nullable=True, index=True)
    tax_identifier = Column(String(100), nullable=True, index=True)

    phone_number = Column(String(30), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=False, default="Edo")

    source_name = Column(String(200), nullable=True)
    source_url = Column(Text, nullable=True)
    discovered_at = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    imported_at = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    tax_year = Column(Integer, nullable=True, index=True)

    matched_taxpayer_id = Column(
        Integer,
        ForeignKey("taxpayers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    match_confidence = Column(Numeric(5, 2), nullable=True)
    match_status = Column(
        String(40),
        nullable=False,
        default="UNREVIEWED",
        index=True,
    )
    verification_status = Column(
        String(40),
        nullable=False,
        default="PENDING",
        index=True,
    )
    review_notes = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    matched_taxpayer = relationship("Taxpayer")

    __table_args__ = (
        Index(
            "ix_business_register_name_city",
            "normalized_name",
            "city",
        ),
    )
