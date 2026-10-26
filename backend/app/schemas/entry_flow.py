from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EntryOption(BaseModel):
    id: str
    label: str
    description: str


class EntryOptionsResponse(BaseModel):
    message: str
    question: str
    options: list[EntryOption]


class EntrySessionStartRequest(BaseModel):
    taxpayer_id: int
    channel: str = "WEB"


class EntrySessionResponse(BaseModel):
    id: int
    taxpayer_id: int
    channel: str
    path: str | None
    status: str
    current_step: str | None
    selected_form_code: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class EntryPathSelectionRequest(BaseModel):
    selection: str


class EntryPathSelectionResponse(BaseModel):
    session_id: int
    path: str
    status: str
    selected_form_code: str | None
    conversation_id: int | None
    message: str
    question: Any | None = None