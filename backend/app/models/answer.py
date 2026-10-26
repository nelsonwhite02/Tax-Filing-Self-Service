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


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # For repeatable sections such as H1/H3 employees.
    #
    # Example:
    # employee-1
    # employee-2
    # employee-3
    #
    # NULL means the answer belongs to the normal
    # non-repeatable conversation flow.
    repeat_group_code = Column(
        String(50),
        nullable=True,
        index=True,
    )

    repeat_instance = Column(
        Integer,
        nullable=True,
    )

    # TEXT, VOICE, FILE, IMAGE, SYSTEM, etc.
    input_type = Column(
        String(30),
        nullable=False,
        default="TEXT",
    )

    # The normalized answer.
    #
    # Examples:
    # "John Doe"
    # 4500000
    # ["employment", "business"]
    # {"amount": 5000000, "currency": "NGN"}
    value_json = Column(
        JSONB,
        nullable=False,
    )

    # Original user wording where useful, especially
    # for AI/voice conversations.
    raw_text = Column(
        String(5000),
        nullable=True,
    )

    # Speech-to-text transcription, when applicable.
    transcription = Column(
        String(10000),
        nullable=True,
    )

    # Reference to stored audio/image/file.
    #
    # We deliberately store a reference rather than
    # binary media in PostgreSQL.
    media_reference = Column(
        String(1000),
        nullable=True,
    )

    # Optional AI extraction information.
    metadata_json = Column(
        JSONB,
        nullable=True,
    )

    sequence = Column(
        Integer,
        nullable=False,
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

    conversation = relationship(
        "Conversation",
        back_populates="answers",
    )

    question = relationship(
        "Question",
    )