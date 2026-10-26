from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConversationStartRequest(BaseModel):
    taxpayer_id: int
    form_code: str = "FORM_A"
    channel: str = "WEB"


class ConversationStartResponse(BaseModel):
    id: int
    taxpayer_id: int
    form_id: int
    status: str
    channel: str
    current_question_id: int | None
    started_at: datetime
    last_activity_at: datetime


class QuestionOptionResponse(BaseModel):
    id: int
    value: str
    label: str
    sequence: int


class QuestionResponse(BaseModel):
    id: int
    code: str
    field_name: str
    data_path: str | None
    prompt: str
    help_text: str | None
    scope: str
    answer_type: str
    required: bool
    sequence: int
    repeat_group_code: str | None
    options: list[QuestionOptionResponse] = []


class CurrentQuestionResponse(BaseModel):
    conversation_id: int
    status: str
    question: QuestionResponse | None


class AnswerSubmitRequest(BaseModel):
    value: Any
    raw_text: str | None = None
    input_type: str = "TEXT"
    transcription: str | None = None
    media_reference: str | None = None
    metadata: dict | None = None
    repeat_group_code: str | None = None
    repeat_instance: int | None = None


class AnswerResponse(BaseModel):
    id: int
    conversation_id: int
    question_id: int | None
    repeat_group_code: str | None
    repeat_instance: int | None
    input_type: str
    value: Any
    raw_text: str | None
    transcription: str | None
    media_reference: str | None
    sequence: int
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    taxpayer_id: int
    form_id: int
    status: str
    channel: str
    current_question_id: int | None
    started_at: datetime
    last_activity_at: datetime
    completed_at: datetime | None
    is_active: bool