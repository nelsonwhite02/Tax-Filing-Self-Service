from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class FormDefinition(Base):
    __tablename__ = "form_definitions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    sections = relationship(
        "FormSection",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormSection.sequence",
    )
    questions = relationship(
        "Question",
        back_populates="form",
        cascade="all, delete-orphan",
    )
    rules = relationship(
        "QuestionRule",
        back_populates="form",
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        back_populates="form",
    )


class FormSection(Base):
    __tablename__ = "form_sections"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(
        Integer,
        ForeignKey("form_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    scope = Column(String(30), nullable=False, default="INDIVIDUAL")
    sequence = Column(Integer, nullable=False)
    repeatable = Column(Boolean, nullable=False, default=False)
    repeat_group_code = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    form = relationship("FormDefinition", back_populates="sections")
    questions = relationship(
        "Question",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="Question.sequence",
    )

    __table_args__ = (
        UniqueConstraint(
            "form_id", "code", name="uq_form_sections_form_code"
        ),
    )


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(
        Integer,
        ForeignKey("form_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id = Column(
        Integer,
        ForeignKey("form_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code = Column(String(100), unique=True, nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    data_path = Column(String(255), nullable=True)

    prompt = Column(Text, nullable=False)
    help_text = Column(Text, nullable=True)

    # INDIVIDUAL, EMPLOYER, EMPLOYEE, SYSTEM
    scope = Column(String(30), nullable=False)

    # text, textarea, number, currency, date, phone, email,
    # boolean, single_choice, multi_choice, file, signature
    answer_type = Column(String(40), nullable=False)

    required = Column(Boolean, nullable=False, default=False)
    sequence = Column(Integer, nullable=False)

    # e.g. "employee"; all EMPLOYEE questions in H1/H3 use this.
    repeat_group_code = Column(String(50), nullable=True)

    # Extensible rules without changing the schema.
    validation_rules = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    form = relationship("FormDefinition", back_populates="questions")
    section = relationship("FormSection", back_populates="questions")

    options = relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.sequence",
    )

    outgoing_rules = relationship(
        "QuestionRule",
        foreign_keys="QuestionRule.source_question_id",
        back_populates="source_question",
        cascade="all, delete-orphan",
    )

    incoming_rules = relationship(
        "QuestionRule",
        foreign_keys="QuestionRule.target_question_id",
        back_populates="target_question",
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value = Column(String(100), nullable=False)
    label = Column(String(255), nullable=False)
    sequence = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    question = relationship("Question", back_populates="options")

    __table_args__ = (
        UniqueConstraint(
            "question_id", "value", name="uq_question_options_question_value"
        ),
    )


class QuestionRule(Base):
    __tablename__ = "question_rules"

    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(
        Integer,
        ForeignKey("form_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # equals, not_equals, contains, not_contains, gt, gte, lt, lte, is_true, is_false
    operator = Column(String(30), nullable=False)

    # JSON allows scalar values or arrays:
    # "yes", 8000000, ["business", "fees"]
    comparison_value = Column(JSONB, nullable=True)

    # SHOW, HIDE, SKIP_TO, REQUIRE
    action = Column(String(30), nullable=False, default="SHOW")

    priority = Column(Integer, nullable=False, default=100)
    metadata_json = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    form = relationship("FormDefinition", back_populates="rules")
    source_question = relationship(
        "Question",
        foreign_keys=[source_question_id],
        back_populates="outgoing_rules",
    )
    target_question = relationship(
        "Question",
        foreign_keys=[target_question_id],
        back_populates="incoming_rules",
    )
