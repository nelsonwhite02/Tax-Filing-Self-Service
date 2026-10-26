from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class EntrySession(Base):
    __tablename__ = "entry_sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    taxpayer_id = Column(
        Integer,
        ForeignKey("taxpayers.id"),
        nullable=False,
        index=True,
    )

    channel = Column(
        String(30),
        nullable=False,
    )

    # MYSELF / MY_EMPLOYEES
    path = Column(
        String(30),
        nullable=True,
    )

    # ACTIVE / FORM_SELECTED /
    # AWAITING_EMPLOYER_CLASSIFICATION /
    # COMPLETED / CANCELLED
    status = Column(
        String(40),
        nullable=False,
        default="ACTIVE",
        index=True,
    )

    # Example:
    # ENTRY
    # EMPLOYER_CLASSIFICATION
    # FORM_SELECTED
    current_step = Column(
        String(100),
        nullable=True,
    )

    # Remains NULL until the system has
    # determined the applicable form.
    selected_form_code = Column(
        String(30),
        nullable=True,
        index=True,
    )

    metadata_json = Column(
        JSONB,
        nullable=True,
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

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    taxpayer = relationship(
        "Taxpayer",
    )