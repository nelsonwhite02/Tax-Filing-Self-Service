"""Idempotent Form A Year of Assessment and rule repair helper.

Run after the existing seed has been corrected to remove malformed add_rule calls.
This helper does not invent option values: it matches existing A_INCOME_SOURCES /
A_ELIGIBLE_DEDUCTIONS option values by semantic token and fails loudly if a mapping
cannot be found. Adapt the aliases below only to values actually present in DB.
"""
from sqlalchemy.orm import Session
from app.models import FormDefinition, FormSection, Question, QuestionOption, QuestionRule

INCOME_TARGET_ALIASES = {
    "A_BUSINESS_INCOME": ("business", "trade", "profession", "vocation"),
    "A_EMPLOYMENT_SALARY": ("employment", "salary", "wages"),
    "A_EMPLOYMENT_BONUS": ("employment", "bonus", "perquisite"),
    "A_RENTAL_INCOME": ("rental", "rent"),
    "A_DIVIDEND_INCOME": ("dividend",),
    "A_FEES_INCOME": ("fees", "fee"),
    "A_ROYALTY_INCOME": ("royalt",),
    "A_INTEREST_INCOME": ("interest",),
    "A_DISCOUNT_REBATE_INCOME": ("discount", "rebate"),
    "A_PREMIUM_INCOME": ("premium",),
    "A_ANNUITY_INCOME": ("annuity",),
    "A_ASSET_DISPOSAL_GAIN": ("asset", "disposal", "gain", "virtual"),
    "A_PRIZES_HONORARIA_AWARDS": ("prize", "honoraria", "award"),
    "A_OTHER_INCOME": ("other_income", "other"),
}
DEDUCTION_TARGET_ALIASES = {
    "A_ANNUAL_RENT_PAID": ("rent",),
    "A_NHF_CONTRIBUTION": ("nhf", "housing_fund"),
    "A_NHIA_CONTRIBUTION": ("nhia", "health_insurance"),
    "A_LIFE_ASSURANCE_PREMIUM": ("life_assurance", "assurance"),
    "A_PENSION": ("pension",),
    "A_HOUSING_LOAN_INTEREST": ("housing_loan_interest", "loan_interest"),
}

def _q(db, form, code):
    return db.query(Question).filter(Question.form_id == form.id, Question.code == code).first()

def _match_option(options, aliases):
    matches = []
    for option in options:
        value = (option.value or "").lower().replace("-", "_")
        if any(alias in value for alias in aliases):
            matches.append(option.value)
    return list(dict.fromkeys(matches))

def patch_form_a_year_and_rules(db: Session) -> None:
    form = db.query(FormDefinition).filter(FormDefinition.code == "FORM_A").first()
    if not form:
        raise ValueError("FORM_A is missing. Run the existing form seed first.")
    section = db.query(FormSection).filter(
        FormSection.form_id == form.id, FormSection.code == "PART_B_IDENTIFICATION"
    ).first()
    if not section:
        raise ValueError("FORM_A section PART_B_IDENTIFICATION is missing.")

    year_q = _q(db, form, "A_TAX_YEAR")
    year_data = dict(
        form_id=form.id, section_id=section.id, code="A_TAX_YEAR",
        field_name="tax_year", data_path="return.tax_year",
        prompt="What Year of Assessment are you filing for?",
        help_text="Enter the four-digit year, for example 2026.",
        scope="INDIVIDUAL", answer_type="number", required=True, sequence=10,
        validation_rules={"min": 2000, "max": 2200}, is_active=True,
    )
    if year_q is None:
        year_q = Question(**year_data)
        db.add(year_q)
    else:
        for key, value in year_data.items():
            if key not in {"form_id", "section_id", "code"}:
                setattr(year_q, key, value)

    # Clear only rules attached to the specific targets this helper owns.
    owned_codes = set(INCOME_TARGET_ALIASES) | set(DEDUCTION_TARGET_ALIASES) | {"A_LOSS_CAPITAL_ALLOWANCE"}
    owned_questions = db.query(Question).filter(
        Question.form_id == form.id, Question.code.in_(owned_codes)
    ).all()
    owned_ids = [q.id for q in owned_questions]
    if owned_ids:
        db.query(QuestionRule).filter(
            QuestionRule.form_id == form.id, QuestionRule.target_question_id.in_(owned_ids)
        ).delete(synchronize_session=False)

    source_income = _q(db, form, "A_INCOME_SOURCES")
    source_deductions = _q(db, form, "A_ELIGIBLE_DEDUCTIONS")
    if not source_income or not source_deductions:
        raise ValueError("Expected A_INCOME_SOURCES and A_ELIGIBLE_DEDUCTIONS questions are missing.")

    income_options = db.query(QuestionOption).filter(
        QuestionOption.question_id == source_income.id, QuestionOption.is_active.is_(True)
    ).all()
    deduction_options = db.query(QuestionOption).filter(
        QuestionOption.question_id == source_deductions.id, QuestionOption.is_active.is_(True)
    ).all()

    def add_contains_rules(source, options, mapping):
        for target_code, aliases in mapping.items():
            target = _q(db, form, target_code)
            if target is None:
                # Some deployments use grouped income questions. Don't invent a question.
                continue
            values = _match_option(options, aliases)
            if not values:
                raise ValueError(
                    f"Cannot map {target_code} to an active option value. "
                    f"Review the actual option values for {source.code}."
                )
            for value in values:
                db.add(QuestionRule(
                    form_id=form.id, source_question_id=source.id, target_question_id=target.id,
                    operator="contains", comparison_value=value, action="SHOW", priority=100, is_active=True,
                ))

    add_contains_rules(source_income, income_options, INCOME_TARGET_ALIASES)
    add_contains_rules(source_deductions, deduction_options, DEDUCTION_TARGET_ALIASES)

    has_loss = _q(db, form, "A_HAS_LOSS_CAPITAL_ALLOWANCE")
    loss_amount = _q(db, form, "A_LOSS_CAPITAL_ALLOWANCE")
    if has_loss and loss_amount:
        db.add(QuestionRule(
            form_id=form.id, source_question_id=has_loss.id, target_question_id=loss_amount.id,
            operator="equals", comparison_value=True, action="SHOW", priority=100, is_active=True,
        ))
    db.commit()
