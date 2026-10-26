from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class TaxAssessment(Base):
    __tablename__ = "tax_assessments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    taxpayer_id = Column(
        Integer,
        ForeignKey("taxpayers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    form_code = Column(
        String(30),
        nullable=False,
        index=True,
    )

    # FORM_A, FORM_H1, FORM_H3
    filing_type = Column(
        String(30),
        nullable=False,
        index=True,
    )

    tax_year = Column(
        Integer,
        nullable=False,
        index=True,
    )

    # Main calculation outputs
    total_income = Column(
        Numeric(18, 2),
        nullable=False,
        default=0,
    )

    total_deductions = Column(
        Numeric(18, 2),
        nullable=False,
        default=0,
    )

    chargeable_income = Column(
        Numeric(18, 2),
        nullable=False,
        default=0,
    )

    tax_payable = Column(
        Numeric(18, 2),
        nullable=False,
        default=0,
    )

    tax_credit = Column(
        Numeric(18, 2),
        nullable=False,
        default=0,
    )

    net_tax_due = Column(
        Numeric(18, 2),
        nullable=False,
        default=0,
    )

    # CALCULATED
    # PRESENTED_TO_TAXPAYER
    # ACCEPTED
    # PAYMENT_PENDING
    # PAID
    # OBJECTED
    # CLOSED
    calculation_status = Column(
        String(40),
        nullable=False,
        default="CALCULATED",
        index=True,
    )

    # Example:
    # EIRS_FORM_A_NTA_2025_V1
    calculation_version = Column(
        String(100),
        nullable=False,
    )

    # Complete calculation trace.
    #
    # This contains:
    # - income components
    # - deduction components
    # - tax-band breakdown
    # - employer employee calculations for H1/H3
    # - calculation rules
    calculation_details = Column(
        JSONB,
        nullable=False,
    )

    # Normalized tax inputs used by the engine.
    #
    # This deliberately contains calculation inputs rather than the entire
    # taxpayer conversation. Sensitive identification answers such as NIN
    # should NOT be copied here.
    input_snapshot = Column(
        JSONB,
        nullable=False,
    )

    notes = Column(
        Text,
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

    presented_at = Column(
        DateTime,
        nullable=True,
    )

    accepted_at = Column(
        DateTime,
        nullable=True,
    )

    objected_at = Column(
        DateTime,
        nullable=True,
    )

    paid_at = Column(
        DateTime,
        nullable=True,
    )

    taxpayer = relationship(
        "Taxpayer",
    )

    conversation = relationship(
        "Conversation",
    )

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            name="uq_tax_assessments_conversation_id",
        ),
    )