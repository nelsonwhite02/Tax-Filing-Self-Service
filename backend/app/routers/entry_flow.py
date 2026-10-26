from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.entry_flow import (
    EntryOptionsResponse,
    EntryPathSelectionRequest,
    EntryPathSelectionResponse,
    EntrySessionResponse,
    EntrySessionStartRequest,
)
from app.services.conversation.entry_flow_service import (
    ConversationEntryService,
)


router = APIRouter(
    prefix="/api/conversation-entry",
    tags=["Conversation Entry"],
)


def _session_response(session):
    return EntrySessionResponse(
        id=session.id,
        taxpayer_id=session.taxpayer_id,
        channel=session.channel,
        path=session.path,
        status=session.status,
        current_step=session.current_step,
        selected_form_code=session.selected_form_code,
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


def _question_response(question):
    if not question:
        return None

    return {
        "id": question.id,
        "code": question.code,
        "field_name": question.field_name,
        "data_path": question.data_path,
        "prompt": question.prompt,
        "help_text": question.help_text,
        "scope": question.scope,
        "answer_type": question.answer_type,
        "required": question.required,
        "sequence": question.sequence,
        "repeat_group_code": question.repeat_group_code,
        "options": [
            {
                "id": option.id,
                "value": option.value,
                "label": option.label,
                "sequence": option.sequence,
            }
            for option in sorted(
                question.options,
                key=lambda item: item.sequence,
            )
        ],
    }


@router.get(
    "/",
    response_model=EntryOptionsResponse,
)
def get_entry_options(
    db: Session = Depends(get_db),
):
    service = ConversationEntryService(db)

    return service.get_entry_options()


@router.post(
    "/start",
    response_model=EntrySessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_entry_session(
    request: EntrySessionStartRequest,
    db: Session = Depends(get_db),
):
    service = ConversationEntryService(db)

    try:
        session = service.start_entry_session(
            taxpayer_id=request.taxpayer_id,
            channel=request.channel,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return _session_response(session)


@router.get(
    "/{session_id}",
    response_model=EntrySessionResponse,
)
def get_entry_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    service = ConversationEntryService(db)

    try:
        session = service.get_session(session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _session_response(session)


@router.post(
    "/{session_id}/select",
    response_model=EntryPathSelectionResponse,
)
def select_entry_path(
    session_id: int,
    request: EntryPathSelectionRequest,
    db: Session = Depends(get_db),
):
    service = ConversationEntryService(db)

    try:
        result = service.select_path(
            session_id=session_id,
            selection=request.selection,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    session = result["session"]
    conversation = result["conversation"]
    question = result["question"]

    if result["path"] == service.MYSELF:
        message = (
            "Great. I'll guide you through your personal "
            "income tax return step by step."
        )
    else:
        message = (
            "I'll first collect the employer information "
            "needed to determine the appropriate EIRS return."
        )

    return EntryPathSelectionResponse(
        session_id=session.id,
        path=result["path"],
        status=session.status,
        selected_form_code=session.selected_form_code,
        conversation_id=(
            conversation.id
            if conversation
            else None
        ),
        message=message,
        question=_question_response(question),
    )


@router.post(
    "/{session_id}/cancel",
    response_model=EntrySessionResponse,
)
def cancel_entry_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    service = ConversationEntryService(db)

    try:
        session = service.cancel_session(session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _session_response(session)