from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)

    taxpayer_id = Column(
        Integer,
        ForeignKey("taxpayers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    form_id = Column(
        Integer,
        ForeignKey("form_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # STARTED, IN_PROGRESS, AWAITING_CLARIFICATION,
    # COMPLETED, ABANDONED, CANCELLED
    status = Column(
        String(40),
        nullable=False,
        default="STARTED",
        index=True,
    )

    # WHATSAPP, WEB, ADMIN
    channel = Column(
        String(30),
        nullable=False,
        default="WHATSAPP",
        index=True,
    )

    current_question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Used for workflow-specific state that does not belong
    # directly to a form answer.
    metadata_json = Column(
        JSONB,
        nullable=True,
    )

    started_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    last_activity_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    taxpayer = relationship(
        "Taxpayer",
        back_populates="conversations",
    )

    form = relationship(
        "FormDefinition",
        back_populates="conversations",
    )

    current_question = relationship(
        "Question",
        foreign_keys=[current_question_id],
    )

    answers = relationship(
        "Answer",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Answer.sequence",
    )