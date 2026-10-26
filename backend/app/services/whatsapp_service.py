import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.tax_assessment_service import TaxAssessmentService

from app.models import Conversation, EntrySession, Taxpayer
from app.services.conversation.conversation_service import (
    ConversationService,
)
from app.services.conversation.entry_flow_service import (
    ConversationEntryService,
)

logger = logging.getLogger(__name__)


class WhatsAppConversationService:
    """
    Connects WhatsApp messages to the channel-independent
    EIRS questionnaire engine.

    WhatsApp-specific responsibilities:
    - Parse text/media/interactive answers
    - Convert WhatsApp selections to question values
    - Pass answers to ConversationService
    - Format questions for WhatsApp
    """

    CHANNEL = "WHATSAPP"
    PAYMENT_BUTTON_ID = "btn_make_payment"
    OBJECTION_BUTTON_ID = "btn_objection"

    def __init__(self, db: Session):
        self.db = db

        self.entry_service = ConversationEntryService(db)

        self.conversation_service = ConversationService(db)

    # ================================================================
    # MAIN MESSAGE HANDLER
    # ================================================================
    def _map_choice_numbers_to_values(
        self,
        question,
        text: str,
        multiple: bool,
    ) -> Any:
        options = sorted(
            [option for option in question.options if option.is_active],
            key=lambda option: option.sequence,
        )

        if not options:
            raise ValueError("No choices are configured for this question.")

        tokens = [
            token.strip()
            for token in text.replace(";", ",").split(",")
            if token.strip()
        ]

        if not tokens:
            raise ValueError("Please select at least one option.")

        values = []
        for token in tokens:
            direct = next(
                (
                    option.value
                    for option in options
                    if str(option.value).lower() == token.lower()
                ),
                None,
            )

            if direct is not None:
                values.append(direct)
                continue

            try:
                number = int(token)
            except ValueError:
                raise ValueError("Please select the option number(s) shown above.")

            if number < 1 or number > len(options):
                raise ValueError(
                    f"Option {number} is not available. Please choose from 1 to {len(options)}."
                )

            values.append(options[number - 1].value)

        values = list(dict.fromkeys(values))

        if multiple:
            return values

        if len(values) != 1:
            raise ValueError("Please select only one option.")

        return values[0]


    def _retry_message(self, question) -> str:
        if not question.required:
            return "If this question does not apply to you, reply SKIP."

        options = [
            option for option in question.options
            if getattr(option, "is_active", True)
        ]
        if options:
            return "Please reply using the option number(s) shown above."

        answer_type = (getattr(question, "answer_type", None) or "").lower()
        if answer_type == "boolean":
            return "Please reply Yes or No."
        if answer_type == "currency":
            return "Please enter the amount in naira, for example ₦250,000."
        if answer_type in {"file", "image", "audio"}:
            return "Please send the requested attachment."
        if answer_type == "signature":
            return "Please type your full name to confirm your declaration."
        return "Please provide a valid answer."


    def _completed_response(self, conversation_id: int) -> dict[str, Any]:
        """Create/retrieve the saved deterministic assessment after completion."""
        try:
            assessment = TaxAssessmentService(self.db).create_assessment(
                conversation_id
            )
        except Exception:
            logger.exception(
                "EIRS assessment creation failed for completed conversation %s",
                conversation_id,
            )
            try:
                self.db.rollback()
            except Exception:
                logger.exception("Rollback failed after assessment error.")
            return {
                "action": "ASSESSMENT_PENDING",
                "conversation_id": conversation_id,
                "message": (
                    "Thank you. Your tax return questionnaire has been completed and saved.\n\n"
                    "EIRS could not finalize your assessment automatically at this time. "
                    "Your submission has been retained for EIRS review. Please do not "
                    "make a payment based on this message."
                ),
            }

        reference = f"EIRS-{assessment.form_code}-{assessment.id:06d}"

        def money(value: Any) -> str:
            return f"₦{float(value or 0):,.2f}"

        return {
            "action": "ASSESSMENT_READY",
            "conversation_id": conversation_id,
            "assessment_id": assessment.id,
            "assessment_reference": reference,
            "tax_year": assessment.tax_year,
            "form_code": assessment.form_code,
            "calculation_status": assessment.calculation_status,
            "message": (
                f"EIRS TAX ASSESSMENT — {assessment.tax_year}\n\n"
                f"Assessment reference: {reference}\n"
                f"Total income: {money(assessment.total_income)}\n"
                f"Total deductions: {money(assessment.total_deductions)}\n"
                f"Chargeable income: {money(assessment.chargeable_income)}\n"
                f"Tax payable: {money(assessment.tax_payable)}\n"
                f"Tax credit: {money(assessment.tax_credit)}\n"
                f"Net tax due: {money(assessment.net_tax_due)}\n\n"
                "This assessment was calculated and recorded by EIRS. "
                "Payment instructions will be provided through an authorized EIRS "
                "payment channel. No payment link has been generated by this message."
            ),
        }

    def handle_message(
        self,
        sender_phone: str,
        message_type: str,
        text: str | None = None,
        media_reference: str | None = None,
        raw_message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        phone = self.normalize_phone(sender_phone)

        taxpayer = self._find_taxpayer(phone)

        # ------------------------------------------------------------
        # Unknown taxpayer
        # ------------------------------------------------------------

        if not taxpayer:
            return {
                "action": "UNKNOWN_TAXPAYER",
                "message": (
                    "This WhatsApp number is not currently linked "
                    "to an EIRS taxpayer record.\n\n"
                    "Please contact EIRS for assistance."
                ),
            }

        # ------------------------------------------------------------
        # Handle restart commands and assessment buttons before the form.
        # ------------------------------------------------------------
        clean_text = (text or "").strip()
        command = clean_text.upper()
        button_id = self._get_button_id(raw_message)

        if button_id == self.PAYMENT_BUTTON_ID:
            return {
                "action": "PAYMENT_FORWARD",
                "message": (
                    "Payment is not enabled for this assessment yet. "
                    "Please wait for official payment instructions from EIRS."
                ),
            }

        if button_id == self.OBJECTION_BUTTON_ID:
            return {
                "action": "OBJECTION_RESPONSE",
                "message": (
                    "If you disagree with this assessment, you may visit your "
                    "nearest EIRS tax office for assistance. Please contact EIRS "
                    "on 08039769389 to confirm the appropriate office."
                ),
            }

        if command in {"START", "RESTART", "RESET"}:
            try:
                active_conversations = (
                    self.db.query(Conversation)
                    .filter(
                        Conversation.taxpayer_id == taxpayer.id,
                        Conversation.channel == self.CHANNEL,
                        Conversation.status == "IN_PROGRESS",
                    )
                    .all()
                )
                for active in active_conversations:
                    active.status = "CANCELLED"
                    if hasattr(active, "is_active"):
                        active.is_active = False

                (self.db.query(EntrySession)
                    .filter(
                        EntrySession.taxpayer_id == taxpayer.id,
                        EntrySession.channel == self.CHANNEL,
                    )
                    .delete(synchronize_session=False))
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("Failed to reset WhatsApp filing session")
                return {
                    "action": "ERROR",
                    "message": "I could not restart your filing session. Please try again shortly.",
                }

            entry_session = self.entry_service.start_entry_session(
                taxpayer_id=taxpayer.id,
                channel=self.CHANNEL,
            )
            return {
                "action": "ENTRY_OPTIONS",
                "taxpayer_id": taxpayer.id,
                "entry_session_id": entry_session.id,
                "message": self._format_entry_options(),
            }

        # ------------------------------------------------------------
        # Find active entry session
        # ------------------------------------------------------------

        entry_session = self._get_active_entry_session(
            taxpayer_id=taxpayer.id
        )

        # ------------------------------------------------------------
        # No active session → create one
        # ------------------------------------------------------------

        if not entry_session:

            entry_session = (
                self.entry_service.start_entry_session(
                    taxpayer_id=taxpayer.id,
                    channel=self.CHANNEL,
                )
            )

            return {
                "action": "ENTRY_OPTIONS",
                "taxpayer_id": taxpayer.id,
                "entry_session_id": entry_session.id,
                "message": self._format_entry_options(),
            }

        # ------------------------------------------------------------
        # ENTRY stage
        # ------------------------------------------------------------

        if (
            entry_session.status
            == self.entry_service.ACTIVE
            and entry_session.current_step == "ENTRY"
        ):

            selection = self._extract_selection(
                text=text,
                raw_message=raw_message,
            )

            return self._handle_entry_selection(
                entry_session.id,
                selection,
            )

        # ------------------------------------------------------------
        # Employer classification
        # ------------------------------------------------------------

        if (
            entry_session.status
            == self.entry_service.AWAITING_EMPLOYER_CLASSIFICATION
        ):

            return {
                "action": "EMPLOYER_CLASSIFICATION",
                "entry_session_id": entry_session.id,
                "message": (
                    "Thank you. I first need to determine the "
                    "appropriate EIRS employer return for your situation."
                ),
            }

        # ------------------------------------------------------------
        # Active FORM conversation
        # ------------------------------------------------------------

        if entry_session.status == self.entry_service.FORM_SELECTED:
            conversation = self._get_active_conversation(taxpayer_id=taxpayer.id)

            if not conversation:
                return {
                    "action": "ERROR",
                    "message": (
                        "I could not find your active tax return conversation. "
                        "Please reply START to begin again."
                    ),
                }

            return self._handle_form_message(
                conversation=conversation,
                message_type=(message_type or "text").lower(),
                text=text,
                media_reference=media_reference,
                raw_message=raw_message,
            )

        return {
            "action": "UNKNOWN_STATE",
            "message": (
                "Your EIRS filing session is in an unexpected state. "
                "Please reply START to begin again."
            ),
        }

    # ================================================================
    # FORM MESSAGE HANDLING
    # ================================================================

    def _handle_form_message(
        self,
        conversation: Conversation,
        message_type: str,
        text: str | None,
        media_reference: str | None,
        raw_message: dict[str, Any] | None,
    ) -> dict[str, Any]:

        question = (
            self.conversation_service.get_current_question(
                conversation.id
            )
        )

        if not question:
            return self._completed_response(conversation.id)

        # ------------------------------------------------------------
        # Media answer
        # ------------------------------------------------------------

        if message_type in {
            "image",
            "document",
            "audio",
        }:

            return self._submit_answer(
                conversation=conversation,
                message_type=message_type,
                text=text,
                media_reference=media_reference,
                raw_message=raw_message,
            )

        # ------------------------------------------------------------
        # Interactive selection
        # ------------------------------------------------------------

        selection = self._extract_selection(
            text=text,
            raw_message=raw_message,
        )

        if selection is not None:

            return self._submit_answer(
                conversation=conversation,
                message_type="text",
                text=selection,
                media_reference=None,
                raw_message=raw_message,
            )

        # ------------------------------------------------------------
        # Text
        # ------------------------------------------------------------

        if message_type == "text":

            if not text or not text.strip():

                return {
                    "action": "VALIDATION_ERROR",
                    "conversation_id": conversation.id,
                    "message": (
                        "I didn't receive an answer. "
                        "Please send your answer and try again."
                    ),
                }

            return self._submit_answer(
                conversation=conversation,
                message_type="text",
                text=text,
                media_reference=None,
                raw_message=raw_message,
            )

        # ------------------------------------------------------------
        # Unsupported
        # ------------------------------------------------------------

        return {
            "action": "UNSUPPORTED_MESSAGE",
            "conversation_id": conversation.id,
            "message": (
                "I can't use that type of message for this question. "
                "Please send the requested information in the format "
                "shown above."
            ),
        }

    # ================================================================
    # TEXT ANSWER
    # ================================================================
    def _submit_answer(
        self,
        conversation: Conversation,
        message_type: str,
        text: str | None,
        media_reference: str | None,
        raw_message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        question = self.conversation_service.get_current_question(conversation.id)

        if not question:
            return self._completed_response(conversation.id)

        try:
            value, input_type, metadata = self._convert_message_to_value(
                question=question,
                message_type=message_type,
                text=text,
                media_reference=media_reference,
                raw_message=raw_message,
            )

            updated_conversation = self.conversation_service.submit_answer(
                conversation_id=conversation.id,
                value=value,
                raw_text=text,
                input_type=input_type,
                media_reference=media_reference,
                metadata=metadata,
            )
        except ValueError as exc:
            return {
                "action": "VALIDATION_ERROR",
                "conversation_id": conversation.id,
                "message": f"{exc}\n\n{self._retry_message(question)}",
            }

        if updated_conversation.status == "COMPLETED":
            return self._completed_response(updated_conversation.id)

        next_question = self.conversation_service.get_current_question(
            updated_conversation.id
        )

        if not next_question:
            return self._completed_response(updated_conversation.id)

        return {
            "action": "QUESTION",
            "conversation_id": updated_conversation.id,
            "message": self._format_question(next_question),
        }


    def _submit_text_answer(
        self,
        conversation: Conversation,
        question,
        text: str,
        raw_message: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        value = self._convert_text_to_value(
            question=question,
            text=text,
        )

        try:

            updated_conversation = (
                self.conversation_service.submit_answer(
                    conversation_id=conversation.id,
                    value=value,
                    raw_text=text,
                    input_type="TEXT",
                    metadata={
                        "channel": self.CHANNEL,
                        "source": "whatsapp_webhook",
                        "raw_message_id": (
                            raw_message.get("id")
                            if raw_message
                            else None
                        ),
                    },
                )
            )

        except ValueError as exc:

            return {
                "action": "VALIDATION_ERROR",
                "conversation_id": conversation.id,
                "message": (
                    f"{exc}\n\n"
                    "Please provide a valid answer and try again."
                ),
            }

        return self._format_submission_result(
            updated_conversation
        )

    # ================================================================
    # MEDIA ANSWER
    # ================================================================

    def _submit_media_answer(
        self,
        conversation: Conversation,
        question,
        message_type: str,
        media_reference: str | None,
        raw_message: dict[str, Any] | None,
    ) -> dict[str, Any]:

        if not media_reference:

            return {
                "action": "VALIDATION_ERROR",
                "conversation_id": conversation.id,
                "message": (
                    "I received the media message, but I could not "
                    "identify the uploaded file. Please send it again."
                ),
            }

        # ------------------------------------------------------------
        # Validate media against question type.
        #
        # FILE currently accepts documents/images.
        # IMAGE explicitly accepts images.
        # AUDIO explicitly accepts audio.
        # ------------------------------------------------------------

        answer_type = question.answer_type.lower()

        allowed = False

        if answer_type in {"file", "image"}:
            allowed = message_type in {
                "image",
                "document",
            }

        elif answer_type == "audio":
            allowed = message_type == "audio"

        if not allowed:

            return {
                "action": "VALIDATION_ERROR",
                "conversation_id": conversation.id,
                "message": (
                    f"This question expects a "
                    f"{question.answer_type.lower()} response. "
                    "Please follow the requested format."
                ),
            }

        try:

            updated_conversation = (
                self.conversation_service.submit_answer(
                    conversation_id=conversation.id,
                    value={
                        "media_id": media_reference,
                        "media_type": message_type,
                    },
                    raw_text=None,
                    input_type=message_type.upper(),
                    media_reference=media_reference,
                    metadata={
                        "channel": self.CHANNEL,
                        "source": "whatsapp_webhook",
                        "raw_message_id": (
                            raw_message.get("id")
                            if raw_message
                            else None
                        ),
                        "media_id": media_reference,
                        "media_type": message_type,
                        "mime_type": (
                            raw_message.get("mime_type")
                            if raw_message
                            else None
                        ),
                        "filename": (
                            raw_message.get("filename")
                            if raw_message
                            else None
                        ),
                        "caption": (
                            raw_message.get("caption")
                            if raw_message
                            else None
                        ),
                    },
                )
            )

        except ValueError as exc:

            return {
                "action": "VALIDATION_ERROR",
                "conversation_id": conversation.id,
                "message": (
                    f"{exc}\n\n"
                    "Please send the requested file again."
                ),
            }

        return self._format_submission_result(
            updated_conversation
        )

    # ================================================================
    # SUBMISSION RESULT
    # ================================================================

    def _format_submission_result(
        self,
        conversation: Conversation,
    ) -> dict[str, Any]:
        if conversation.status == "COMPLETED":
            return self._completed_response(conversation.id)

        next_question = self.conversation_service.get_current_question(
            conversation.id
        )
        if not next_question:
            return self._completed_response(conversation.id)

        return {
            "action": "QUESTION",
            "conversation_id": conversation.id,
            "message": self._format_question(next_question),
        }

    # ================================================================
    # ENTRY SELECTION
    # ================================================================

    def _handle_entry_selection(
        self,
        entry_session_id: int,
        selection: str | None,
    ) -> dict[str, Any]:

        if not selection:

            return {
                "action": "ENTRY_OPTIONS",
                "entry_session_id": entry_session_id,
                "message": self._format_entry_options(),
            }

        normalized = selection.strip().lower()

        if normalized in {
            "1",
            "myself",
            "me",
            "my own",
            "my own return",
        }:

            selected_path = self.entry_service.MYSELF

        elif normalized in {
            "2",
            "my employees",
            "employees",
            "my employee",
        }:

            selected_path = self.entry_service.MY_EMPLOYEES

        else:

            return {
                "action": "ENTRY_OPTIONS",
                "entry_session_id": entry_session_id,
                "message": (
                    "Please choose one of the following options:\n\n"
                    "1. Myself\n"
                    "2. My employees\n\n"
                    "Reply with 1 or 2."
                ),
            }

        result = self.entry_service.select_path(
            session_id=entry_session_id,
            selection=selected_path,
        )

        if selected_path == self.entry_service.MYSELF:

            question = result["question"]

            return {
                "action": "QUESTION",
                "entry_session_id": result["session"].id,
                "conversation_id": result["conversation"].id,
                "message": (
                    "Great. I'll guide you through your personal "
                    "income tax return step by step.\n\n"
                    + self._format_question(question)
                ),
            }

        return {
            "action": "EMPLOYER_CLASSIFICATION",
            "entry_session_id": result["session"].id,
            "message": (
                "Thank you. I'll first collect the employer "
                "information needed to determine the appropriate "
                "EIRS return."
            ),
        }

    def _get_button_id(self, raw_message: dict[str, Any] | None) -> str | None:
        if not isinstance(raw_message, dict):
            return None
        direct = raw_message.get("button_id")
        if direct:
            return str(direct)
        interactive = raw_message.get("interactive")
        if isinstance(interactive, dict):
            reply = interactive.get("button_reply") or interactive.get("list_reply")
            if isinstance(reply, dict) and reply.get("id"):
                return str(reply["id"])
        return None

    # ================================================================
    # SELECTION EXTRACTION
    # ================================================================

    def _extract_selection(
        self,
        text: str | None,
        raw_message: dict[str, Any] | None,
    ) -> str | None:

        if raw_message:

            selection_id = raw_message.get(
                "selection_id"
            )

            if selection_id:
                return str(selection_id)

            button_id = raw_message.get("button_id")

            if button_id:
                return str(button_id)

            list_id = raw_message.get("list_id")

            if list_id:
                return str(list_id)

            selection_title = raw_message.get(
                "selection_title"
            )

            if selection_title:
                return str(selection_title)

            button_title = raw_message.get(
                "button_title"
            )

            if button_title:
                return str(button_title)

            list_title = raw_message.get(
                "list_title"
            )

            if list_title:
                return str(list_title)

        if text is not None:
            return text.strip()

        return None

    # ================================================================
    # VALUE CONVERSION
    # ================================================================

    def _convert_message_to_value(
        self,
        question,
        message_type: str,
        text: str | None,
        media_reference: str | None,
        raw_message: dict[str, Any] | None,
    ) -> tuple[Any, str, dict[str, Any]]:
        answer_type = (question.answer_type or "text").lower()
        message_type = (message_type or "text").lower()
        cleaned = (text or "").strip()

        metadata = {
            "channel": "WHATSAPP",
            "source": "whatsapp_webhook",
            "message_type": message_type,
            "raw_message_id": raw_message.get("id") if raw_message else None,
        }

        # A declaration/signature is captured as a typed full name, not an upload.
       
        # A Boolean declaration confirmation must be converted to True/False.
        # Do not mistake it for a typed signature just because its code or
        # prompt contains the word "declaration".
        signature_text = " ".join(
            str(getattr(question, attr, "") or "")
            for attr in ("code", "field_name", "prompt", "help_text")
        ).lower()

        is_boolean = answer_type in {"boolean", "bool"}

        is_signature = (
            answer_type == "signature"
            or (
                not is_boolean
                and "signature" in signature_text
            )
            or (
                not is_boolean
                and "declaration" in signature_text
            )
        )

        if is_signature:
            if message_type in {"image", "document", "audio", "file"} or media_reference:
                raise ValueError("Please type your full name to confirm your declaration; do not send an attachment.")
            if not cleaned:
                raise ValueError("Please type your full name to confirm your declaration.")
            return cleaned, "TEXT", metadata

        # SKIP is accepted only for optional questions. Persist None as the answer value.
        if cleaned.lower() in {"skip", "none", "n/a", "na", "not applicable"}:
            if question.required:
                raise ValueError("This question is required and cannot be skipped.")
            metadata["skipped"] = True
            return None, "TEXT", metadata

        if not cleaned and message_type == "text":
            if question.required:
                raise ValueError("This question requires an answer.")
            metadata["skipped"] = True
            return None, "TEXT", metadata

        # FILE / IMAGE / AUDIO questions accept media.
        if answer_type in {"file", "image", "audio"}:
            if not media_reference:
                raise ValueError("Please send the requested file or media attachment.")

            allowed = {
                "file": {"image", "document", "file"},
                "image": {"image"},
                "audio": {"audio"},
            }[answer_type]

            if message_type not in allowed:
                raise ValueError(f"Please send the requested {answer_type} attachment.")

            metadata["media_reference"] = media_reference
            return {"media_type": message_type}, message_type.upper(), metadata

        # Boolean: Yes/No and 1/2.
        if answer_type == "boolean":
            normalized = cleaned.strip().lower()

            if normalized in {"yes", "y", "true", "1"}:
                return True, "TEXT", metadata

            if normalized in {"no", "n", "false", "0", "2"}:
                return False, "TEXT", metadata

            raise ValueError(
                f"'{question.code}' expects true or false.\n"
                "Please reply Yes or No."
            )

        # Currency.
        if answer_type == "currency":
            numeric = (
                cleaned.replace(",", "")
                .replace("₦", "")
                .replace("NGN", "")
                .replace("ngn", "")
                .strip()
            )
            try:
                return float(numeric), "TEXT", metadata
            except ValueError:
                raise ValueError(
                    "Please enter a valid amount, for example 250000 or ₦250,000."
                )

        # Number.
        if answer_type == "number":
            try:
                return int(cleaned), "TEXT", metadata
            except ValueError:
                raise ValueError("Please enter a valid number.")

        # Multi-choice: "1,3" -> actual QuestionOption values.
        if answer_type == "multi_choice":
            return (
                self._map_choice_numbers_to_values(question, cleaned, multiple=True),
                "TEXT",
                metadata,
            )

        # Single-choice: "2" -> actual QuestionOption value.
        if answer_type == "single_choice":
            return (
                self._map_choice_numbers_to_values(question, cleaned, multiple=False),
                "TEXT",
                metadata,
            )

        return cleaned, "TEXT", metadata

    # ================================================================
    # MULTI-CHOICE CONVERSION
    # ================================================================

    def _convert_multi_choice(
        self,
        question,
        text: str,
    ) -> list[str]:

        parts = [
            item.strip()
            for item in text.split(",")
            if item.strip()
        ]

        if not parts:

            raise ValueError(
                "Please select at least one option."
            )

        options = sorted(
            question.options,
            key=lambda option: option.sequence,
        )

        converted: list[str] = []

        for part in parts:

            # Numeric WhatsApp selection:
            # 1 -> first option
            if part.isdigit():

                index = int(part)

                if index < 1 or index > len(options):

                    raise ValueError(
                        "One of your selected option numbers "
                        "is not valid. Please choose from the "
                        "options shown."
                    )

                option = options[index - 1]

                value = self._option_value(option)

                converted.append(value)

                continue

            # Already supplied actual value.
            matched = self._find_option_by_value(
                options,
                part,
            )

            if matched:

                converted.append(
                    self._option_value(matched)
                )

                continue

            # Allow exact label.
            matched = self._find_option_by_label(
                options,
                part,
            )

            if matched:

                converted.append(
                    self._option_value(matched)
                )

                continue

            raise ValueError(
                f"'{part}' is not one of the available options."
            )

        # Remove duplicates while preserving order.
        return list(dict.fromkeys(converted))

    # ================================================================
    # SINGLE-CHOICE CONVERSION
    # ================================================================

    def _convert_single_choice(
        self,
        question,
        text: str,
    ) -> str:

        options = sorted(
            question.options,
            key=lambda option: option.sequence,
        )

        if text.isdigit():

            index = int(text)

            if index < 1 or index > len(options):

                raise ValueError(
                    "Please choose one of the numbered options shown."
                )

            return self._option_value(
                options[index - 1]
            )

        matched = self._find_option_by_value(
            options,
            text,
        )

        if matched:

            return self._option_value(matched)

        matched = self._find_option_by_label(
            options,
            text,
        )

        if matched:

            return self._option_value(matched)

        raise ValueError(
            "Please choose one of the available options."
        )

    # ================================================================
    # OPTION HELPERS
    # ================================================================

    @staticmethod
    def _option_value(option) -> str:

        value = getattr(option, "value", None)

        if value is not None:
            return str(value)

        code = getattr(option, "code", None)

        if code is not None:
            return str(code)

        label = getattr(option, "label", None)

        if label is not None:
            return str(label)

        raise ValueError(
            "A configured question option is missing its value."
        )

    @staticmethod
    def _find_option_by_value(
        options,
        value: str,
    ):

        normalized = value.strip().lower()

        for option in options:

            option_value = getattr(
                option,
                "value",
                None,
            )

            if option_value is not None:

                if str(option_value).strip().lower() == normalized:
                    return option

            option_code = getattr(
                option,
                "code",
                None,
            )

            if option_code is not None:

                if str(option_code).strip().lower() == normalized:
                    return option

        return None

    @staticmethod
    def _find_option_by_label(
        options,
        label: str,
    ):

        normalized = label.strip().lower()

        for option in options:

            option_label = getattr(
                option,
                "label",
                None,
            )

            if option_label is not None:

                if (
                    str(option_label)
                    .strip()
                    .lower()
                    == normalized
                ):
                    return option

        return None

    # ================================================================
    # QUESTION FORMATTING
    # ================================================================

    def _format_question(self, question) -> str:
        message = question.prompt.strip()

        if question.help_text:
            message += "\n\n" + question.help_text.strip()

        options = sorted(
            [option for option in question.options if option.is_active],
            key=lambda option: option.sequence,
        )

        if options:
            message += "\n\n"
            for index, option in enumerate(options, start=1):
                message += f"{index}. {option.label}\n"

            answer_type = (question.answer_type or "").lower()
            if answer_type == "multi_choice":
                message += "\nYou can select more than one, for example: 1,3."
            elif answer_type == "single_choice":
                message += "\nReply with one option number."

        if not question.required:
            message += "\n\nIf this does not apply to you, reply SKIP."

        return message



    # ================================================================
    # ENTRY OPTIONS
    # ================================================================

    def _format_entry_options(self) -> str:

        options = self.entry_service.get_entry_options()

        message = (
            options["message"]
            + "\n\n"
            + options["question"]
            + "\n\n"
        )

        for index, option in enumerate(
            options["options"],
            start=1,
        ):

            message += (
                f"{index}. {option['label']}\n"
                f"   {option['description']}\n\n"
            )

        message += "Reply with 1 or 2."

        return message

    # ================================================================
    # TAXPAYER LOOKUP
    # ================================================================

    def _find_taxpayer(
        self,
        phone: str,
    ) -> Taxpayer | None:

        taxpayers = (
            self.db.query(Taxpayer)
            .filter(
                Taxpayer.is_active.is_(True),
            )
            .all()
        )

        for taxpayer in taxpayers:

            candidates = [
                getattr(taxpayer, "whatsapp_number", None),
                getattr(taxpayer, "phone", None),
            ]
            for candidate in candidates:
                if candidate and self.normalize_phone(str(candidate)) == phone:
                    return taxpayer

        return None

    # ================================================================
    # ENTRY SESSION LOOKUP
    # ================================================================

    def _get_active_entry_session(
        self,
        taxpayer_id: int,
    ) -> EntrySession | None:

        return (
            self.db.query(EntrySession)
            .filter(
                EntrySession.taxpayer_id == taxpayer_id,
                EntrySession.channel == self.CHANNEL,
                EntrySession.status.in_(
                    [
                        self.entry_service.ACTIVE,
                        self.entry_service.FORM_SELECTED,
                        self.entry_service.AWAITING_EMPLOYER_CLASSIFICATION,
                    ]
                ),
            )
            .order_by(
                EntrySession.created_at.desc()
            )
            .first()
        )

    # ================================================================
    # CONVERSATION LOOKUP
    # ================================================================

    def _get_active_conversation(
        self,
        taxpayer_id: int,
    ) -> Conversation | None:

        return (
            self.db.query(Conversation)
            .filter(
                Conversation.taxpayer_id == taxpayer_id,
                Conversation.channel == self.CHANNEL,
                Conversation.status == "IN_PROGRESS",
                Conversation.is_active.is_(True),
            )
            .order_by(
                Conversation.started_at.desc()
            )
            .first()
        )

    # ================================================================
    # PHONE NORMALIZATION
    # ================================================================

    @staticmethod
    def normalize_phone(phone: str) -> str:
        if not phone:
            return ""
        phone = (
            str(phone)
            .strip()
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        if phone.startswith("+"):
            phone = phone[1:]

        if phone.startswith("0"):
            phone = "234" + phone[1:]

        return phone