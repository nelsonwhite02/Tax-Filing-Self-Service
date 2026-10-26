from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import EntrySession, Taxpayer
from app.services.conversation.conversation_service import (
    ConversationService,
)


class ConversationEntryService:
    """
    Persistent taxpayer entry flow.

    The taxpayer chooses who they are filing for.
    The system determines the actual EIRS form internally.
    """

    MYSELF = "MYSELF"
    MY_EMPLOYEES = "MY_EMPLOYEES"

    ACTIVE = "ACTIVE"
    FORM_SELECTED = "FORM_SELECTED"
    AWAITING_EMPLOYER_CLASSIFICATION = (
        "AWAITING_EMPLOYER_CLASSIFICATION"
    )
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    def __init__(self, db: Session):
        self.db = db
        self.conversation_service = ConversationService(db)

    def get_entry_options(self) -> dict[str, Any]:
        return {
            "message": (
                "Welcome to the EIRS Tax Filing Assistant. "
                "I'll guide you through your tax return step by step. "
                "You don't need to know which tax form to use."
            ),
            "question": "Who are you filing for?",
            "options": [
                {
                    "id": self.MYSELF,
                    "label": "Myself",
                    "description": (
                        "I am filing my own personal tax return."
                    ),
                },
                {
                    "id": self.MY_EMPLOYEES,
                    "label": "My employees",
                    "description": (
                        "I am filing an employer return for employees."
                    ),
                },
            ],
        }

    def start_entry_session(
        self,
        taxpayer_id: int,
        channel: str = "WEB",
    ) -> EntrySession:
        taxpayer = (
            self.db.query(Taxpayer)
            .filter(
                Taxpayer.id == taxpayer_id,
                Taxpayer.is_active.is_(True),
            )
            .first()
        )

        if not taxpayer:
            raise ValueError(
                f"Active taxpayer {taxpayer_id} was not found."
            )

        # Resume an existing active entry session instead of
        # creating multiple simultaneous entry sessions.
        existing = (
            self.db.query(EntrySession)
            .filter(
                EntrySession.taxpayer_id == taxpayer_id,
                EntrySession.channel == channel,
                EntrySession.status.in_(
                    [
                        self.ACTIVE,
                        self.AWAITING_EMPLOYER_CLASSIFICATION,
                    ]
                ),
            )
            .order_by(EntrySession.created_at.desc())
            .first()
        )

        if existing:
            return existing

        session = EntrySession(
            taxpayer_id=taxpayer_id,
            channel=channel,
            path=None,
            status=self.ACTIVE,
            current_step="ENTRY",
            selected_form_code=None,
            metadata_json={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def select_path(
        self,
        session_id: int,
        selection: str,
    ) -> dict[str, Any]:

        session = self._get_session(session_id)

        if session.status not in (
            self.ACTIVE,
            self.AWAITING_EMPLOYER_CLASSIFICATION,
        ):
            raise ValueError(
                "This entry session is no longer accepting "
                "a filing-path selection."
            )

        selection = selection.upper().strip()

        if selection == self.MYSELF:
            return self._select_myself(session)

        if selection == self.MY_EMPLOYEES:
            return self._select_my_employees(session)

        raise ValueError(
            "Invalid filing option. "
            "Please select 'MYSELF' or 'MY_EMPLOYEES'."
        )

    def get_session(
        self,
        session_id: int,
    ) -> EntrySession:
        return self._get_session(session_id)

    def cancel_session(
        self,
        session_id: int,
    ) -> EntrySession:
        session = self._get_session(session_id)

        if session.status in (
            self.COMPLETED,
            self.CANCELLED,
        ):
            return session

        session.status = self.CANCELLED
        session.current_step = None
        session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(session)

        return session

    def _select_myself(
        self,
        session: EntrySession,
    ) -> dict[str, Any]:

        # Internal mapping:
        #
        # MYSELF -> FORM_A
        #
        # The taxpayer never chooses FORM_A.

        conversation = self.conversation_service.start_conversation(
            taxpayer_id=session.taxpayer_id,
            form_code="FORM_A",
            channel=session.channel,
        )

        session.path = self.MYSELF
        session.selected_form_code = "FORM_A"
        session.status = self.FORM_SELECTED
        session.current_step = "FORM_SELECTED"
        session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(session)

        question = self.conversation_service.get_current_question(
            conversation.id
        )

        return {
            "session": session,
            "path": self.MYSELF,
            "conversation": conversation,
            "question": question,
        }

    def _select_my_employees(
        self,
        session: EntrySession,
    ) -> dict[str, Any]:

        session.path = self.MY_EMPLOYEES
        session.selected_form_code = None
        session.status = (
            self.AWAITING_EMPLOYER_CLASSIFICATION
        )
        session.current_step = "EMPLOYER_CLASSIFICATION"
        session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(session)

        return {
            "session": session,
            "path": self.MY_EMPLOYEES,
            "conversation": None,
            "question": None,
        }

    def _get_session(
        self,
        session_id: int,
    ) -> EntrySession:
        session = (
            self.db.query(EntrySession)
            .filter(
                EntrySession.id == session_id,
            )
            .first()
        )

        if not session:
            raise ValueError(
                f"Entry session {session_id} was not found."
            )

        return session