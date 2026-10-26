"""
EIRS Tax Assessment Service
===========================

Adapter between completed EIRS conversations, saved Answer rows, the
deterministic EIRSTaxCalculationEngine, and the TaxAssessment database model.

Responsibilities:
- Accept only a completed conversation and an explicit tax year.
- Read saved answers using stable question codes/field names, not question text.
- Normalize Form A answers using the engine's canonical normalizer.
- Extract H1/H3 employee answers without merging employees together.
- Persist an auditable input snapshot and calculation result.
- Be idempotent for repeated completion/webhook calls.
- Roll back failed database writes and handle a concurrent duplicate attempt.

This service does not contain tax formulas and does not create payment links.
Payment creation and taxpayer notifications belong in separate workflow services.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Answer, Conversation, FormDefinition, Question
from app.models.tax_assessment import TaxAssessment
from app.services.tax_calculation_engine import (
    EIRSTaxCalculationEngine,
    normalize_form_answers,
)


_MONEY_QUANTUM = Decimal("0.01")
_SUPPORTED_FORMS = {"FORM_A", "FORM_H1", "FORM_H3"}


class TaxAssessmentService:
    """Create one deterministic, persisted assessment for a completed filing."""

    # Keys are normalized (lowercase, underscores) question.field_name values
    # or stable question codes. Map only known fields; never infer from prompt
    # text because prompt wording may change between form versions.
    EMPLOYEE_FIELD_ALIASES: dict[str, str] = {
        "name": "name",
        "employee_name": "name",
        "full_name": "name",
        "employee_full_name": "name",
        "designation": "designation",
        "position": "designation",
        "job_title": "designation",
        "employee_designation": "designation",
        "individual_tax_id": "individual_tax_id",
        "tax_id": "individual_tax_id",
        "individual_rin": "individual_tax_id",
        "rin": "individual_tax_id",
        "annual_basic_salary": "annual_basic_salary",
        "basic_salary": "annual_basic_salary",
        "rent": "rent_cash_kind",
        "rent_cash_kind": "rent_cash_kind",
        "rent_in_cash_kind": "rent_cash_kind",
        "annual_rent": "rent_cash_kind",
        "rent_allowance": "rent_cash_kind",
        "transport": "transport_cash_kind",
        "transport_cash_kind": "transport_cash_kind",
        "transport_in_cash_kind": "transport_cash_kind",
        "annual_transport": "transport_cash_kind",
        "transport_allowance": "transport_cash_kind",
        "leave_bonus_allowance": "leave_bonus_allowance",
        "leave_bonus": "leave_bonus_allowance",
        "leave_allowance": "leave_bonus_allowance",
        "thirteenth_month_salary": "thirteenth_month_salary",
        "13th_month_salary": "thirteenth_month_salary",
        "thirteenth_month": "thirteenth_month_salary",
        "other_allowances": "other_allowances",
        "total_allowances": "total_salary_allowances",
        "total_salary_allowances": "total_salary_allowances",
        "total_salary_allowance": "total_salary_allowances",
        "benefit_in_kind": "benefit_in_kind",
        "annual_tax_reliefs": "annual_tax_reliefs",
        "tax_reliefs": "annual_tax_reliefs",
        "annual_tax_deducted": "annual_tax_deducted",
        "tax_deducted": "annual_tax_deducted",
        "paye_deducted": "annual_tax_deducted",
        "nhf_contribution": "nhf_contribution",
        "nhia_contribution": "nhia_contribution",
        "life_assurance_premium": "life_assurance_premium",
        "pension": "pension",
        "pension_contribution": "pension",
        "housing_loan_interest": "housing_loan_interest",
    }

    def __init__(
        self,
        db: Session,
        engine: EIRSTaxCalculationEngine | None = None,
    ) -> None:
        self.db = db
        self.engine = engine or EIRSTaxCalculationEngine()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def create_assessment(
        self,
        conversation_id: int,
        *,
        tax_year: int | None = None,
    ) -> TaxAssessment:
        """
        Calculate and persist an assessment.

        `tax_year` must be supplied by the calling workflow from an explicit
        Year of Assessment answer or a trusted, explicitly configured value.
        This method deliberately does not default to the current calendar year.
        """
        if isinstance(conversation_id, bool) or not isinstance(conversation_id, int):
            raise ValueError("conversation_id must be an integer.")

        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} was not found.")

        if str(conversation.status or "").upper() != "COMPLETED":
            raise ValueError(
                "An assessment can only be created after the conversation is "
                f"completed; current status is {conversation.status!r}."
            )

        # Return the original result on retries; do not silently recalculate an
        # already-issued assessment with possibly changed code/rules.
        existing = self._get_existing_assessment(conversation.id)
        if existing is not None:
            return existing

        form_id = getattr(conversation, "form_id", None)
        form = (
            self.db.query(FormDefinition)
            .filter(FormDefinition.id == form_id)
            .first()
            if form_id is not None
            else None
        )
        form_code = str(getattr(form, "code", "") or "").strip().upper()

        if form_code not in _SUPPORTED_FORMS:
            raise ValueError(
                f"Unsupported or missing form definition for conversation "
                f"{conversation.id}: {form_code or 'unknown form'}."
            )

        answer_rows = self._load_answer_rows(conversation.id)
        if not answer_rows:
            raise ValueError(
                f"Completed conversation {conversation.id} has no saved answers."
            )

        answer_year = self._year_from_answers(answer_rows, form_code)
        if tax_year is None:
            tax_year = answer_year
        elif answer_year is not None and int(tax_year) != answer_year:
            raise ValueError(
                f"Provided tax year {tax_year} does not match the saved Year of Assessment {answer_year}."
            )
        self._validate_tax_year(tax_year)

        # Compute everything before adding a database row. Calculation errors
        # therefore cannot leave a partially populated assessment behind.
        if form_code == "FORM_A":
            result, input_snapshot = self._calculate_form_a(
                answer_rows,
                tax_year=tax_year,
            )
            result_payload = result.as_dict()
            assessment_values = {
                "total_income": result.total_income,
                "total_deductions": result.gross_deductions,
                "chargeable_income": result.chargeable_income,
                "tax_payable": result.tax_payable,
                "tax_credit": result.tax_credit,
                "net_tax_due": result.net_tax_due,
                "calculation_version": result.calculation_version,
            }
        else:
            employees = self._extract_employees(answer_rows)
            if not employees:
                raise ValueError(
                    f"{form_code} conversation has no employee answer groups. "
                    "Check question scope, repeat_group_code, and repeat_instance."
                )

            result_payload = self.engine.calculate_employer_return(
                employees,
                tax_year=tax_year,
                form_code=form_code,
            )
            calculation_fields = {
                "annual_basic_salary",
                "rent_cash_kind",
                "transport_cash_kind",
                "leave_bonus_allowance",
                "thirteenth_month_salary",
                "other_allowances",
                "total_salary_allowances",
                "benefit_in_kind",
                "annual_tax_reliefs",
                "annual_tax_deducted",
                "nhf_contribution",
                "nhia_contribution",
                "life_assurance_premium",
                "pension",
                "housing_loan_interest",
            }
            # Employee names, phone numbers, designations, and tax identifiers
            # are not needed in the tax-input snapshot.
            safe_employees = [
                {key: value for key, value in employee.items() if key in calculation_fields}
                for employee in employees
            ]
            input_snapshot = {
                "form_code": form_code,
                "tax_year": tax_year,
                "employees": self._json_safe(safe_employees),
            }
            assessment_values = {
                "total_income": result_payload.get("total_income"),
                "total_deductions": result_payload.get("total_deductions"),
                "chargeable_income": result_payload.get("chargeable_income"),
                "tax_payable": result_payload.get("tax_payable"),
                "tax_credit": result_payload.get("tax_credit"),
                "net_tax_due": result_payload.get("net_tax_due"),
                "calculation_version": result_payload.get("calculation_version"),
            }

        self._validate_calculation_output(
            assessment_values,
            form_code=form_code,
        )

        now = datetime.utcnow()
        assessment = TaxAssessment(
            taxpayer_id=conversation.taxpayer_id,
            conversation_id=conversation.id,
            form_code=form_code,
            filing_type=form_code,
            tax_year=tax_year,
            total_income=self._to_decimal(assessment_values["total_income"]),
            total_deductions=self._to_decimal(assessment_values["total_deductions"]),
            chargeable_income=self._to_decimal(assessment_values["chargeable_income"]),
            tax_payable=self._to_decimal(assessment_values["tax_payable"]),
            tax_credit=self._to_decimal(assessment_values["tax_credit"]),
            net_tax_due=self._to_decimal(assessment_values["net_tax_due"]),
            calculation_status="CALCULATED",
            calculation_version=str(assessment_values["calculation_version"]),
            calculation_details=self._json_safe(result_payload),
            input_snapshot=self._json_safe(input_snapshot),
            created_at=now,
            updated_at=now,
        )

        self.db.add(assessment)
        try:
            self.db.commit()
            self.db.refresh(assessment)
            return assessment
        except IntegrityError:
            # A unique constraint on tax_assessments.conversation_id is the
            # final guard against two workers processing the same completion.
            self.db.rollback()
            existing = self._get_existing_assessment(conversation.id)
            if existing is not None:
                return existing
            raise
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _year_from_answers(
        rows: list[tuple[Answer, Question]], form_code: str
    ) -> int | None:
        expected_codes = {
            "FORM_A": {"A_TAX_YEAR"},
            "FORM_H1": {"H1_YEAR"},
            "FORM_H3": {"H3_YEAR"},
        }.get(form_code, set())
        for answer, question in rows:
            if (question.code or "").upper() not in expected_codes:
                continue
            value = TaxAssessmentService._answer_value(answer)
            if isinstance(value, bool):
                raise ValueError("Year of Assessment must be a four-digit year.")
            try:
                numeric = Decimal(str(value).strip())
            except Exception as exc:
                raise ValueError("Year of Assessment must be a four-digit year.") from exc
            if numeric != numeric.to_integral_value():
                raise ValueError("Year of Assessment must be a whole number.")
            return int(numeric)
        return None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _get_existing_assessment(self, conversation_id: int) -> TaxAssessment | None:
        return (
            self.db.query(TaxAssessment)
            .filter(TaxAssessment.conversation_id == conversation_id)
            .first()
        )

    def _load_answer_rows(
        self,
        conversation_id: int,
    ) -> list[tuple[Answer, Question]]:
        return (
            self.db.query(Answer, Question)
            .join(Question, Answer.question_id == Question.id)
            .filter(Answer.conversation_id == conversation_id)
            .order_by(Answer.sequence.asc(), Answer.id.asc())
            .all()
        )

    @staticmethod
    def _answer_value(answer: Answer) -> Any:
        """Unwrap the standard {"value": ...} Answer.value_json payload."""
        payload = answer.value_json
        if isinstance(payload, dict) and "value" in payload:
            return payload.get("value")
        return payload

    # ------------------------------------------------------------------
    # Form A
    # ------------------------------------------------------------------

    def _calculate_form_a(
        self,
        rows: list[tuple[Answer, Question]],
        *,
        tax_year: int,
    ) -> tuple[Any, dict[str, Any]]:
        raw_answers: dict[str, Any] = {}

        for answer, question in rows:
            code = str(getattr(question, "code", "") or "").strip()
            if not code:
                continue
            value = self._answer_value(answer)
            # Preserve meaningful false/zero values; omit only unanswered nulls.
            if value is not None:
                raw_answers[code] = value

        normalized = normalize_form_answers(raw_answers)
        if not normalized:
            raise ValueError(
                "No recognized Form A income/deduction answers were found. "
                "Check the seeded question codes against normalize_form_answers()."
            )

        result = self.engine.calculate_form_a(normalized, tax_year=tax_year)
        # Keep the audit snapshot limited to tax calculation inputs. The
        # full answer map above is used only for normalization; it can contain
        # identification answers (including NIN), which must not be copied
        # into the TaxAssessment.input_snapshot JSONB column.
        calculation_question_codes = {
            "A_BUSINESS_INCOME",
            "A_EMPLOYMENT_SALARY",
            "A_EMPLOYMENT_BONUS",
            "A_RENTAL_INCOME",
            "A_DIVIDEND_INCOME",
            "A_FEES_INCOME",
            "A_ROYALTY_INCOME",
            "A_INTEREST_INCOME",
            "A_DISCOUNT_REBATE_INCOME",
            "A_PREMIUM_INCOME",
            "A_ANNUITY_INCOME",
            "A_ASSET_DISPOSAL_GAIN",
            "A_PRIZES_HONORARIA_AWARDS",
            "A_OTHER_INCOME",
            "A_LOSS_CAPITAL_ALLOWANCE",
            "A_ANNUAL_RENT_PAID",
            "A_NHF_CONTRIBUTION",
            "A_NHIA_CONTRIBUTION",
            "A_LIFE_ASSURANCE_PREMIUM",
            "A_PENSION",
            "A_HOUSING_LOAN_INTEREST",
            "A_TAX_CREDIT_REFUND",
        }
        safe_raw_answers = {
            code: value
            for code, value in raw_answers.items()
            if code in calculation_question_codes
        }
        snapshot = {
            "form_code": "FORM_A",
            "tax_year": tax_year,
            "raw_answers_by_question_code": self._json_safe(safe_raw_answers),
            "normalized_tax_inputs": self._json_safe(normalized),
        }
        return result, snapshot

    # ------------------------------------------------------------------
    # H1 / H3 employee repeat groups
    # ------------------------------------------------------------------

    def _extract_employees(
        self,
        rows: list[tuple[Answer, Question]],
    ) -> list[dict[str, Any]]:
        grouped: dict[int, dict[str, Any]] = {}
        recognized_answer_count = 0

        for answer, question in rows:
            question_scope = str(getattr(question, "scope", "") or "").strip().upper()
            question_repeat_code = str(
                getattr(question, "repeat_group_code", "") or ""
            ).strip().lower()
            answer_repeat_code = str(
                getattr(answer, "repeat_group_code", "") or ""
            ).strip().lower()

            is_employee_question = (
                "EMPLOYEE" in question_scope
                or question_repeat_code in {"employee", "employees"}
                or answer_repeat_code in {"employee", "employees"}
            )
            if not is_employee_question:
                continue

            value = self._answer_value(answer)
            if value is None:
                continue

            instance = answer.repeat_instance
            if instance is None:
                if value not in ("", [], {}):
                    raise ValueError(
                        f"Employee answer for question {getattr(question, 'code', '?')!r} "
                        "has no repeat_instance. Refusing to merge employees."
                    )
                continue

            try:
                instance_key = int(instance)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid employee repeat_instance {instance!r}."
                ) from exc
            if instance_key < 0:
                raise ValueError("Employee repeat_instance cannot be negative.")

            raw_field = (
                getattr(question, "field_name", None)
                or getattr(question, "code", None)
                or ""
            )
            canonical_field = self._canonical_employee_field(str(raw_field))
            if canonical_field is None:
                # An unknown employee question is not passed to the tax engine.
                # Keep an audit warning rather than accidentally treating it as
                # a monetary input or guessing based on display text.
                continue

            employee = grouped.setdefault(instance_key, {})
            employee[canonical_field] = value
            recognized_answer_count += 1

        if not grouped or recognized_answer_count == 0:
            return []

        employees: list[dict[str, Any]] = []
        for index in sorted(grouped):
            employee = grouped[index]
            # An employee record must contain at least one recognized income,
            # deduction, credit, or identity field. Identity alone is not enough
            # to calculate a meaningful return.
            has_calculation_field = any(
                key in employee
                for key in (
                    "annual_basic_salary",
                    "rent_cash_kind",
                    "transport_cash_kind",
                    "leave_bonus_allowance",
                    "thirteenth_month_salary",
                    "other_allowances",
                    "total_salary_allowances",
                    "benefit_in_kind",
                    "annual_tax_reliefs",
                    "annual_tax_deducted",
                    "nhf_contribution",
                    "nhia_contribution",
                    "life_assurance_premium",
                    "pension",
                    "housing_loan_interest",
                )
            )
            if not has_calculation_field:
                raise ValueError(
                    f"Employee repeat instance {index} has no recognized "
                    "calculation fields. Check the H1/H3 seed field names."
                )
            employees.append(employee)

        return employees

    @classmethod
    def _canonical_employee_field(cls, raw_field: str) -> str | None:
        key = raw_field.strip().lower()
        key = key.replace(" ", "_").replace("-", "_").replace("/", "_")
        key = "".join(key.split())
        while "__" in key:
            key = key.replace("__", "_")

        if key in cls.EMPLOYEE_FIELD_ALIASES:
            return cls.EMPLOYEE_FIELD_ALIASES[key]

        # Support known aliases embedded in stable, prefixed question codes.
        prefixes = (
            "h1_employee_",
            "h3_employee_",
            "employee_",
            "h1_",
            "h3_",
        )
        for prefix in prefixes:
            if key.startswith(prefix):
                suffix = key[len(prefix):]
                if suffix in cls.EMPLOYEE_FIELD_ALIASES:
                    return cls.EMPLOYEE_FIELD_ALIASES[suffix]

        # Match only complete known suffixes, longest first. This is not prompt
        # matching and will not map an unrelated question by accident.
        for alias in sorted(cls.EMPLOYEE_FIELD_ALIASES, key=len, reverse=True):
            if key.endswith("_" + alias):
                return cls.EMPLOYEE_FIELD_ALIASES[alias]
        return None

    # ------------------------------------------------------------------
    # Validation and serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_tax_year(tax_year: int) -> None:
        if isinstance(tax_year, bool) or not isinstance(tax_year, int):
            raise ValueError("tax_year must be an explicit integer year of assessment.")
        if tax_year < 2000 or tax_year > 2200:
            raise ValueError("tax_year is outside the accepted range 2000–2200.")

    @classmethod
    def _validate_calculation_output(
        cls,
        values: Mapping[str, Any],
        *,
        form_code: str,
    ) -> None:
        required = (
            "total_income",
            "total_deductions",
            "chargeable_income",
            "tax_payable",
            "tax_credit",
            "net_tax_due",
            "calculation_version",
        )
        missing = [key for key in required if values.get(key) is None]
        if missing:
            raise ValueError(
                f"{form_code} calculation returned incomplete output: "
                + ", ".join(missing)
            )
        if not str(values["calculation_version"]).strip():
            raise ValueError(f"{form_code} calculation returned no version.")

        for key in required[:-1]:
            amount = cls._to_decimal(values[key])
            if not amount.is_finite() or amount < 0:
                raise ValueError(
                    f"{form_code} calculation returned invalid {key}: {values[key]!r}."
                )

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0.00")
        if isinstance(value, bool):
            raise ValueError("Boolean values cannot be used as monetary amounts.")
        try:
            amount = value if isinstance(value, Decimal) else Decimal(str(value))
            if not amount.is_finite():
                raise ValueError("Monetary amounts must be finite numbers.")
            return amount.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid monetary amount: {value!r}.") from exc

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        """Convert calculation/input objects into JSONB-safe primitive values."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("Non-finite Decimal cannot be stored in JSON.")
            return float(value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP))
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Mapping):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._json_safe(item) for item in value]
        if hasattr(value, "as_dict") and callable(value.as_dict):
            return cls._json_safe(value.as_dict())
        if hasattr(value, "__dataclass_fields__"):
            return cls._json_safe(
                {
                    key: getattr(value, key)
                    for key in value.__dataclass_fields__
                }
            )
        # Avoid silently serializing arbitrary ORM objects or unsupported types.
        raise TypeError(
            f"Unsupported value for JSONB assessment snapshot: {type(value).__name__}."
        )
