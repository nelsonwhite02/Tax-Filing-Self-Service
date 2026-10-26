
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Answer,
    Conversation,
    FormDefinition,
    Question,
    QuestionRule,
)


class ConversationService:
    """Channel-independent questionnaire engine."""

    SKIPPED_VALUE = None

    def __init__(self, db: Session):
        self.db = db

    # ================================================================
    # START
    # ================================================================

    def start_conversation(
        self,
        taxpayer_id: int,
        form_code: str = "FORM_A",
        channel: str = "WHATSAPP",
    ) -> Conversation:
        form = (
            self.db.query(FormDefinition)
            .filter(
                FormDefinition.code == form_code,
                FormDefinition.is_active.is_(True),
            )
            .first()
        )
        if not form:
            raise ValueError(f"Active form '{form_code}' was not found.")

        now = datetime.utcnow()
        conversation = Conversation(
            taxpayer_id=taxpayer_id,
            form_id=form.id,
            status="IN_PROGRESS",
            channel=channel,
            is_active=True,
            started_at=now,
            last_activity_at=now,
        )

        try:
            self.db.add(conversation)
            self.db.flush()

            first_question = self._find_next_question(
                conversation=conversation,
                current_question=None,
            )
            if first_question:
                conversation.current_question_id = first_question.id
            else:
                self._complete(conversation)

            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except Exception:
            self.db.rollback()
            raise

    # ================================================================
    # CURRENT QUESTION
    # ================================================================

    def get_current_question(
        self,
        conversation_id: int,
    ) -> Question | None:
        conversation = self._get_conversation(conversation_id)

        if not conversation.current_question_id:
            return None

        question = (
            self.db.query(Question)
            .options(joinedload(Question.options))
            .filter(
                Question.id == conversation.current_question_id,
                Question.is_active.is_(True),
            )
            .first()
        )

        # Never expose internal/system-only questions to a taxpayer.
        if question and (question.scope or "").upper() == "SYSTEM":
            return None

        return question

    # ================================================================
    # SUBMIT ANSWER
    # ================================================================

    def submit_answer(
        self,
        conversation_id: int,
        value: Any,
        raw_text: str | None = None,
        input_type: str = "TEXT",
        transcription: str | None = None,
        media_reference: str | None = None,
        metadata: dict | None = None,
        repeat_group_code: str | None = None,
        repeat_instance: int | None = None,
    ) -> Conversation:
        conversation = self._get_conversation(conversation_id)

        if conversation.status != "IN_PROGRESS" or not conversation.is_active:
            raise ValueError(
                "Conversation is not accepting answers. "
                f"Current status: {conversation.status}"
            )

        question = self.get_current_question(conversation_id)
        if question is None:
            raise ValueError("This conversation has no current question.")

        if self._is_employee_question(question) and repeat_instance is None:
            repeat_instance = self._next_repeat_instance(
                conversation, question
            )
            if repeat_instance is None:
                raise ValueError(
                    "Could not determine the employee instance for this answer."
                )

        text = str(raw_text if raw_text is not None else value or "").strip()
        is_skip = text.upper() == "SKIP"
        is_signature = self._is_signature_question(question)

        # Optional questions may be skipped explicitly. Store null plus a
        # skip marker; never convert SKIP to zero.
        if is_skip:
            if question.required:
                raise ValueError(
                    f"'{question.code}' is required and cannot be skipped."
                )
            value = self.SKIPPED_VALUE
            input_type = "TEXT"
            media_reference = None
            metadata = dict(metadata or {})
            metadata["skipped"] = True
            raw_text = "SKIP"

        # A typed name is the declaration signature. Do not treat an arbitrary
        # image as a verified signature. Image-based signature acceptance
        # should only be added later with an appropriate verification process.
        elif is_signature:
            if not text:
                raise ValueError(
                    "Please type your full name to sign the declaration."
                )
            if len(text) < 2:
                raise ValueError("Please enter a valid full name.")
            value = text
            raw_text = text
            input_type = "TEXT"
            media_reference = None
            metadata = dict(metadata or {})
            metadata["signature_method"] = "typed_name"

        else:
            self._validate_answer(
                question=question,
                value=value,
                input_type=input_type,
                media_reference=media_reference,
            )

        try:
            last_answer = (
                self.db.query(Answer)
                .filter(Answer.conversation_id == conversation.id)
                .order_by(Answer.sequence.desc())
                .first()
            )
            sequence = last_answer.sequence + 1 if last_answer else 1
            now = datetime.utcnow()

            answer = Answer(
                conversation_id=conversation.id,
                question_id=question.id,
                repeat_group_code=(
                    repeat_group_code
                    if repeat_group_code is not None
                    else question.repeat_group_code
                ),
                repeat_instance=repeat_instance,
                input_type=input_type,
                value_json={
                    "value": value,
                    "skipped": bool(is_skip),
                },
                raw_text=raw_text,
                transcription=transcription,
                media_reference=media_reference,
                metadata_json=metadata,
                sequence=sequence,
                created_at=now,
                updated_at=now,
            )
            self.db.add(answer)
            self.db.flush()

            conversation.last_activity_at = now
            next_question = self._find_next_question(
                conversation=conversation,
                current_question=question,
            )

            if next_question:
                conversation.current_question_id = next_question.id
            else:
                conversation.current_question_id = None
                self._complete(conversation)

            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except Exception:
            self.db.rollback()
            raise

    # ================================================================
    # CANCEL / COMPLETION
    # ================================================================

    def cancel_conversation(
        self,
        conversation_id: int,
    ) -> Conversation:
        conversation = self._get_conversation(conversation_id)
        conversation.status = "CANCELLED"
        conversation.is_active = False
        conversation.current_question_id = None
        conversation.last_activity_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    @staticmethod
    def _complete(conversation: Conversation) -> None:
        now = datetime.utcnow()
        conversation.status = "COMPLETED"
        conversation.is_active = False
        conversation.current_question_id = None
        conversation.completed_at = now
        conversation.last_activity_at = now

    # ================================================================
    # QUESTION ORDER / PROGRESSION
    # ================================================================

    def _find_next_question(
        self,
        conversation: Conversation,
        current_question: Question | None,
    ) -> Question | None:
        questions = (
            self.db.query(Question)
            .options(
                joinedload(Question.options),
                joinedload(Question.section),
            )
            .filter(
                Question.form_id == conversation.form_id,
                Question.is_active.is_(True),
            )
            .all()
        )
        questions.sort(
            key=lambda q: (
                q.section.sequence if q.section else 0,
                q.sequence,
                q.id,
            )
        )

        current_index = -1
        if current_question is not None:
            current_index = next(
                (i for i, q in enumerate(questions)
                 if q.id == current_question.id),
                -1,
            )

        # Employee section: finish remaining fields for this employee, then
        # repeat from the first employee field for the next employee.
        if (
            current_question is not None
            and self._is_employee_question(current_question)
        ):
            latest = (
                self.db.query(Answer)
                .filter(
                    Answer.conversation_id == conversation.id,
                    Answer.question_id == current_question.id,
                )
                .order_by(Answer.sequence.desc())
                .first()
            )
            instance = latest.repeat_instance if latest else None
            if instance is None:
                raise ValueError(
                    f"Employee answer '{current_question.code}' "
                    "has no repeat_instance."
                )

            employee_questions = [
                q for q in questions if self._is_employee_question(q)
            ]

            for q in employee_questions:
                if questions.index(q) <= current_index:
                    continue
                if self._question_has_answer(
                    conversation.id, q.id, int(instance)
                ):
                    continue
                if self._question_is_applicable(conversation, q):
                    return q

            count = self._employee_count(conversation)
            if int(instance) < count and employee_questions:
                first_employee = employee_questions[0]
                if (
                    not self._question_has_answer(
                        conversation.id, first_employee.id, int(instance) + 1
                    )
                    and self._question_is_applicable(
                        conversation, first_employee
                    )
                ):
                    return first_employee

            if employee_questions:
                current_index = max(
                    questions.index(q) for q in employee_questions
                )

        # On a new conversation, start at the beginning. On later turns,
        # continue after the current question. Existing answers are respected.
        for q in questions[current_index + 1:]:
            if (q.scope or "").upper() == "SYSTEM":
                continue

            if self._is_employee_question(q):
                count = self._employee_count(conversation)
                if count < 1:
                    raise ValueError(
                        "Employee return requires a valid employee count "
                        "before employee details."
                    )
                instance = self._next_repeat_instance(
                    conversation, q, employee_count=count
                )
                if instance is None:
                    continue
            elif self._question_has_any_answer(conversation.id, q.id):
                continue

            if self._question_is_applicable(conversation, q):
                return q

        return None

    @staticmethod
    def _is_employee_question(question: Question) -> bool:
        return (
            (getattr(question, "scope", "") or "").upper() == "EMPLOYEE"
            or (getattr(question, "repeat_group_code", None) or "").lower()
            == "employee"
        )

    @staticmethod
    def _is_signature_question(question: Question) -> bool:
        code = (getattr(question, "code", "") or "").lower()
        field = (getattr(question, "field_name", "") or "").lower()
        prompt = (getattr(question, "prompt", "") or "").lower()

        # Restrict this exception to actual declaration/signature fields.
        return (
            "signature" in code
            or "signature" in field
            or ("signature" in prompt and "declaration" in prompt)
        )

    def _employee_count(self, conversation: Conversation) -> int:
        rows = (
            self.db.query(Answer, Question)
            .join(Question, Answer.question_id == Question.id)
            .filter(Answer.conversation_id == conversation.id)
            .order_by(Answer.sequence.desc())
            .all()
        )
        for answer, question in rows:
            code = (question.code or "").upper()
            field_name = (
                getattr(question, "field_name", "") or ""
            ).lower()
            if (
                code in {"H1_EMPLOYEE_COUNT", "H3_EMPLOYEE_COUNT"}
                or field_name == "employee_count"
            ):
                value = self._get_answer_value(answer)
                try:
                    count = int(value)
                except (TypeError, ValueError):
                    raise ValueError("Employee count must be a whole number.")
                if count < 1 or count > 5000:
                    raise ValueError(
                        "Employee count must be between 1 and 5000."
                    )
                return count
        return 0

    def _next_repeat_instance(
        self,
        conversation: Conversation,
        question: Question,
        employee_count: int | None = None,
    ) -> int | None:
        count = (
            employee_count
            if employee_count is not None
            else self._employee_count(conversation)
        )
        if count < 1:
            return None

        answered = {
            int(instance)
            for (instance,) in self.db.query(Answer.repeat_instance)
            .filter(
                Answer.conversation_id == conversation.id,
                Answer.question_id == question.id,
                Answer.repeat_instance.isnot(None),
            )
            .all()
        }
        for instance in range(1, count + 1):
            if instance not in answered:
                return instance
        return None

    def _question_has_answer(
        self, conversation_id: int, question_id: int, repeat_instance: int
    ) -> bool:
        return self.db.query(Answer.id).filter(
            Answer.conversation_id == conversation_id,
            Answer.question_id == question_id,
            Answer.repeat_instance == repeat_instance,
        ).first() is not None

    def _question_has_any_answer(
        self, conversation_id: int, question_id: int
    ) -> bool:
        return self.db.query(Answer.id).filter(
            Answer.conversation_id == conversation_id,
            Answer.question_id == question_id,
        ).first() is not None

    @staticmethod
    def _get_answer_value(answer: Answer) -> Any:
        payload = answer.value_json
        if isinstance(payload, dict) and "value" in payload:
            return payload["value"]
        return payload

    # ================================================================
    # CONDITIONAL RULES
    # ================================================================

    def _question_is_applicable(
        self,
        conversation: Conversation,
        question: Question,
    ) -> bool:
        rules = (
            self.db.query(QuestionRule)
            .filter(
                QuestionRule.target_question_id == question.id,
                QuestionRule.is_active.is_(True),
            )
            .order_by(
                QuestionRule.priority.desc(),
                QuestionRule.id,
            )
            .all()
        )

        if not rules:
            return True

        for rule in rules:
            source_value = self._get_latest_answer_value(
                conversation, rule.source_question_id
            )
            if self._evaluate_rule(
                source_value,
                rule.operator,
                rule.comparison_value,
            ) and rule.action == "SHOW":
                return True

        return False

    def _evaluate_rule(
        self,
        source_value: Any,
        operator: str,
        comparison_value: Any,
    ) -> bool:
        if source_value is None:
            return False

        if operator == "equals":
            return source_value == comparison_value
        if operator == "not_equals":
            return source_value != comparison_value
        if operator == "contains":
            if isinstance(source_value, list):
                return comparison_value in source_value
            if isinstance(source_value, str):
                return str(comparison_value).lower() in source_value.lower()
            return False
        if operator == "not_contains":
            if isinstance(source_value, list):
                return comparison_value not in source_value
            if isinstance(source_value, str):
                return str(comparison_value).lower() not in source_value.lower()
            return False

        try:
            left = float(source_value)
            right = float(comparison_value)
        except (TypeError, ValueError):
            return False

        comparisons = {
            "greater_than": left > right,
            "gt": left > right,
            "less_than": left < right,
            "lt": left < right,
            "greater_than_or_equal": left >= right,
            "gte": left >= right,
            "less_than_or_equal": left <= right,
            "lte": left <= right,
        }
        return comparisons.get(operator, False)

    def _get_latest_answer_value(
        self,
        conversation: Conversation,
        question_id: int,
    ) -> Any:
        answer = (
            self.db.query(Answer)
            .filter(
                Answer.conversation_id == conversation.id,
                Answer.question_id == question_id,
            )
            .order_by(Answer.sequence.desc())
            .first()
        )
        if answer is None or not answer.value_json:
            return None
        return self._get_answer_value(answer)

    # ================================================================
    # VALIDATION
    # ================================================================

    def _validate_answer(
        self,
        question: Question,
        value: Any,
        input_type: str = "TEXT",
        media_reference: str | None = None,
    ) -> None:
        answer_type = (question.answer_type or "text").lower()

        if question.required and (value is None or value == ""):
            raise ValueError(f"'{question.code}' requires an answer.")

        if value is None and not media_reference:
            if question.required:
                raise ValueError(f"'{question.code}' requires an answer.")
            return

        if answer_type in {"file", "image", "audio", "signature"}:
            if not media_reference:
                raise ValueError(
                    f"'{question.code}' requires the requested file/media."
                )
            return

        if answer_type == "multi_choice":
            if not isinstance(value, list):
                raise ValueError(
                    f"'{question.code}' expects multiple selections."
                )
            valid_values = {
                option.value for option in question.options if option.is_active
            }
            invalid = [item for item in value if item not in valid_values]
            if invalid:
                raise ValueError(
                    f"Invalid option(s) for '{question.code}': "
                    + ", ".join(map(str, invalid))
                )
            return

        if answer_type == "single_choice":
            valid_values = {
                option.value for option in question.options if option.is_active
            }
            if value not in valid_values:
                raise ValueError(f"Invalid selection for '{question.code}'.")
            return

        if answer_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"'{question.code}' expects true or false.")
            return

        if answer_type in {"currency", "number"}:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"'{question.code}' expects a numeric amount."
                )

            rules = question.validation_rules or {}
            if rules.get("min") is not None and number < rules["min"]:
                raise ValueError(
                    f"'{question.code}' must be at least {rules['min']}."
                )
            if rules.get("max") is not None and number > rules["max"]:
                raise ValueError(
                    f"'{question.code}' must not exceed {rules['max']}."
                )
            if answer_type == "currency" and number < 0:
                raise ValueError(f"'{question.code}' cannot be negative.")

    # ================================================================
    # LOOKUP
    # ================================================================

    def _get_conversation(
        self,
        conversation_id: int,
    ) -> Conversation:
        conversation = (
            self.db.query(Conversation)
            .options(joinedload(Conversation.answers))
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if not conversation:
            raise ValueError(
                f"Conversation {conversation_id} was not found."
            )
        return conversation
