from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Answer, Conversation
from app.schemas.conversation import (
    AnswerResponse,
    AnswerSubmitRequest,
    ConversationResponse,
    ConversationStartRequest,
    ConversationStartResponse,
    CurrentQuestionResponse,
    QuestionOptionResponse,
    QuestionResponse,
)
from app.services.conversation.conversation_service import ConversationService


router = APIRouter(
    prefix="/api/conversations",
    tags=["Conversations"],
)


def _question_to_response(question) -> QuestionResponse:
    return QuestionResponse(
        id=question.id,
        code=question.code,
        field_name=question.field_name,
        data_path=question.data_path,
        prompt=question.prompt,
        help_text=question.help_text,
        scope=question.scope,
        answer_type=question.answer_type,
        required=question.required,
        sequence=question.sequence,
        repeat_group_code=question.repeat_group_code,
        options=[
            QuestionOptionResponse(
                id=option.id,
                value=option.value,
                label=option.label,
                sequence=option.sequence,
            )
            for option in sorted(
                question.options,
                key=lambda item: item.sequence,
            )
        ],
    )


def _conversation_to_response(conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        taxpayer_id=conversation.taxpayer_id,
        form_id=conversation.form_id,
        status=conversation.status,
        channel=conversation.channel,
        current_question_id=conversation.current_question_id,
        started_at=conversation.started_at,
        last_activity_at=conversation.last_activity_at,
        completed_at=conversation.completed_at,
        is_active=conversation.is_active,
    )


@router.post(
    "/start",
    response_model=ConversationStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_conversation(
    request: ConversationStartRequest,
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    try:
        conversation = service.start_conversation(
            taxpayer_id=request.taxpayer_id,
            form_code=request.form_code,
            channel=request.channel,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ConversationStartResponse(
        id=conversation.id,
        taxpayer_id=conversation.taxpayer_id,
        form_id=conversation.form_id,
        status=conversation.status,
        channel=conversation.channel,
        current_question_id=conversation.current_question_id,
        started_at=conversation.started_at,
        last_activity_at=conversation.last_activity_at,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} was not found.",
        )

    return _conversation_to_response(conversation)


@router.get(
    "/{conversation_id}/current-question",
    response_model=CurrentQuestionResponse,
)
def get_current_question(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    try:
        conversation = service._get_conversation(conversation_id)
        question = service.get_current_question(conversation_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return CurrentQuestionResponse(
        conversation_id=conversation.id,
        status=conversation.status,
        question=(
            _question_to_response(question)
            if question
            else None
        ),
    )


@router.post(
    "/{conversation_id}/answers",
    response_model=CurrentQuestionResponse,
)
def submit_answer(
    conversation_id: int,
    request: AnswerSubmitRequest,
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    try:
        conversation = service.submit_answer(
            conversation_id=conversation_id,
            value=request.value,
            raw_text=request.raw_text,
            input_type=request.input_type,
            transcription=request.transcription,
            media_reference=request.media_reference,
            metadata=request.metadata,
            repeat_group_code=request.repeat_group_code,
            repeat_instance=request.repeat_instance,
        )

        question = service.get_current_question(conversation.id)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return CurrentQuestionResponse(
        conversation_id=conversation.id,
        status=conversation.status,
        question=(
            _question_to_response(question)
            if question
            else None
        ),
    )


@router.post(
    "/{conversation_id}/cancel",
    response_model=ConversationResponse,
)
def cancel_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    try:
        conversation = service.cancel_conversation(
            conversation_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return _conversation_to_response(conversation)


@router.get(
    "/{conversation_id}/answers",
    response_model=list[AnswerResponse],
)
def get_answers(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} was not found.",
        )

    answers = (
        db.query(Answer)
        .filter(Answer.conversation_id == conversation_id)
        .order_by(Answer.sequence)
        .all()
    )

    return [
        AnswerResponse(
            id=answer.id,
            conversation_id=answer.conversation_id,
            question_id=answer.question_id,
            repeat_group_code=answer.repeat_group_code,
            repeat_instance=answer.repeat_instance,
            input_type=answer.input_type,
            value=(
                answer.value_json.get("value")
                if answer.value_json
                else None
            ),
            raw_text=answer.raw_text,
            transcription=answer.transcription,
            media_reference=answer.media_reference,
            sequence=answer.sequence,
            created_at=answer.created_at,
        )
        for answer in answers
    ]