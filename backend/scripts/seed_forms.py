from datetime import datetime

from app.core.database import SessionLocal
from app.models.form_definition import (
    FormDefinition,
    FormSection,
    Question,
    QuestionOption,
    QuestionRule,
)


def get_or_create_form(db, code, name, description):
    form = (
        db.query(FormDefinition)
        .filter(FormDefinition.code == code)
        .first()
    )

    if not form:
        form = FormDefinition(
            code=code,
            name=name,
            description=description,
            version=1,
            is_active=True,
        )
        db.add(form)
        db.flush()
    else:
        form.name = name
        form.description = description
        form.is_active = True

    return form


def get_or_create_section(
    db,
    form,
    code,
    title,
    scope,
    sequence,
    repeatable=False,
    repeat_group_code=None,
):
    section = (
        db.query(FormSection)
        .filter(
            FormSection.form_id == form.id,
            FormSection.code == code,
        )
        .first()
    )

    if not section:
        section = FormSection(
            form_id=form.id,
            code=code,
            title=title,
            scope=scope,
            sequence=sequence,
            repeatable=repeatable,
            repeat_group_code=repeat_group_code,
            is_active=True,
        )
        db.add(section)
        db.flush()
    else:
        section.title = title
        section.scope = scope
        section.sequence = sequence
        section.repeatable = repeatable
        section.repeat_group_code = repeat_group_code
        section.is_active = True

    return section


def get_or_create_question(
    db,
    form,
    section,
    code,
    field_name,
    prompt,
    answer_type,
    sequence,
    *,
    data_path=None,
    help_text=None,
    scope="INDIVIDUAL",
    required=False,
    repeat_group_code=None,
    validation_rules=None,
    metadata_json=None,
):
    question = (
        db.query(Question)
        .filter(Question.code == code)
        .first()
    )

    if not question:
        question = Question(
            form_id=form.id,
            section_id=section.id,
            code=code,
            field_name=field_name,
            data_path=data_path,
            prompt=prompt,
            help_text=help_text,
            scope=scope,
            answer_type=answer_type,
            required=required,
            sequence=sequence,
            repeat_group_code=repeat_group_code,
            validation_rules=validation_rules,
            metadata_json=metadata_json,
            is_active=True,
        )
        db.add(question)
        db.flush()
    else:
        question.form_id = form.id
        question.section_id = section.id
        question.field_name = field_name
        question.data_path = data_path
        question.prompt = prompt
        question.help_text = help_text
        question.scope = scope
        question.answer_type = answer_type
        question.required = required
        question.sequence = sequence
        question.repeat_group_code = repeat_group_code
        question.validation_rules = validation_rules
        question.metadata_json = metadata_json
        question.is_active = True

    return question


def add_options(db, question, options):
    """
    options:
        [
            ("value", "Human label"),
            ...
        ]
    """

    for sequence, (value, label) in enumerate(options, start=1):
        option = (
            db.query(QuestionOption)
            .filter(
                QuestionOption.question_id == question.id,
                QuestionOption.value == value,
            )
            .first()
        )

        if not option:
            option = QuestionOption(
                question_id=question.id,
                value=value,
                label=label,
                sequence=sequence,
                is_active=True,
            )
            db.add(option)
        else:
            option.label = label
            option.sequence = sequence
            option.is_active = True


def add_rule(
    db,
    form,
    source_question,
    target_question,
    operator,
    comparison_value,
    action="SHOW",
    priority=100,
):
    existing = (
        db.query(QuestionRule)
        .filter(
            QuestionRule.form_id == form.id,
            QuestionRule.source_question_id == source_question.id,
            QuestionRule.target_question_id == target_question.id,
            QuestionRule.operator == operator,
        )
        .first()
    )

    if not existing:
        existing = QuestionRule(
            form_id=form.id,
            source_question_id=source_question.id,
            target_question_id=target_question.id,
            operator=operator,
            comparison_value=comparison_value,
            action=action,
            priority=priority,
            is_active=True,
        )
        db.add(existing)
    else:
        existing.comparison_value = comparison_value
        existing.action = action
        existing.priority = priority
        existing.is_active = True


# ============================================================
# FORM A
# ============================================================

def seed_form_a(db):
    form = get_or_create_form(
        db,
        "FORM_A",
        "Form A — Personal Income Tax Return",
        (
            "Personal Income Tax Return for individuals with income "
            "accruing in, derived from, brought into or received in Nigeria."
        ),
    )

    # --------------------------------------------------------
    # PART B — IDENTIFICATION
    # --------------------------------------------------------

    identification = get_or_create_section(
        db,
        form,
        "PART_B_IDENTIFICATION",
        "Part B — Identification",
        "INDIVIDUAL",
        1,
    )

    q_full_name = get_or_create_question(
        db,
        form,
        identification,
        "A_FULL_NAME",
        "full_name",
        "What is your full name?",
        "text",
        1,
        data_path="taxpayer.full_name",
        required=True,
    )

    q_address = get_or_create_question(
        db,
        form,
        identification,
        "A_RESIDENTIAL_ADDRESS",
        "residential_address",
        "What is your residential address?",
        "textarea",
        2,
        data_path="taxpayer.address",
        required=True,
    )

    q_tax_id = get_or_create_question(
        db,
        form,
        identification,
        "A_TAX_ID",
        "tax_id",
        "What is your Tax ID/RIN, if you have one?",
        "text",
        3,
        data_path="taxpayer.tax_id",
        required=False,
    )

    q_nin = get_or_create_question(
        db,
        form,
        identification,
        "A_NIN",
        "nin",
        "What is your NIN?",
        "text",
        4,
        data_path="taxpayer.nin",
        required=False,
        metadata_json={
            "sensitive": True,
            "secure_storage": True,
        },
    )

    q_phone = get_or_create_question(
        db,
        form,
        identification,
        "A_PHONE",
        "phone",
        "What telephone number should EIRS use to contact you?",
        "phone",
        5,
        data_path="taxpayer.phone_number",
        required=True,
    )

    q_email = get_or_create_question(
        db,
        form,
        identification,
        "A_EMAIL",
        "email",
        "What is your email address?",
        "email",
        6,
        data_path="taxpayer.email",
        required=False,
    )

    q_business_name = get_or_create_question(
        db,
        form,
        identification,
        "A_BUSINESS_NAME",
        "business_name",
        "If you operate a business, what is the business name?",
        "text",
        7,
        data_path="taxpayer.business_name",
        required=False,
    )

    q_business_address = get_or_create_question(
        db,
        form,
        identification,
        "A_BUSINESS_ADDRESS",
        "business_address",
        "What is the address of the business, if applicable?",
        "textarea",
        8,
        data_path="taxpayer.business_address",
        required=False,
    )

    get_or_create_question(
        db,
        form,
        identification,
        "A_PASSPORT_PHOTOGRAPH",
        "passport_photograph",
        "Please provide your passport photograph.",
        "file",
        9,
        data_path="taxpayer.passport_photograph",
        required=False,
        metadata_json={
            "accepted_types": ["image/jpeg", "image/png"],
        },
    )

    # --------------------------------------------------------
    # PART C — INCOME
    # --------------------------------------------------------

    income = get_or_create_section(
        db,
        form,
        "PART_C_INCOME",
        "Part C — Computation of Chargeable Income",
        "INDIVIDUAL",
        2,
    )

    q_income_sources = get_or_create_question(
        db,
        form,
        income,
        "A_INCOME_SOURCES",
        "income_sources",
        "Which types of income did you receive during the year?",
        "multi_choice",
        1,
        data_path="part_c.income_sources",
        required=True,
        metadata_json={
            "conversation_role": "income_discovery",
        },
    )

    add_options(
        db,
        q_income_sources,
        [
            ("employment", "Salary, wages or employment income"),
            ("business", "Business, trade, profession or vocation"),
            ("rent", "Rent"),
            ("dividends", "Dividends"),
            ("fees", "Fees"),
            ("royalties", "Royalties"),
            ("interest", "Interest"),
            ("discounts_rebates", "Discounts or rebates"),
            ("premium", "Premium"),
            ("annuity", "Annuity"),
            ("asset_disposal", "Gains from disposal of assets, including property or virtual assets"),
            ("prizes_awards", "Prizes, honoraria or awards"),
            ("other", "Other income"),
        ],
    )

    q_business_income = get_or_create_question(
        db,
        form,
        income,
        "A_BUSINESS_INCOME",
        "business_income",
        "What was your total income from trade, business, profession or vocation for the year?",
        "currency",
        2,
        data_path="part_c.business_income",
        required=False,
    )

    q_salary = get_or_create_question(
        db,
        form,
        income,
        "A_EMPLOYMENT_SALARY",
        "employment_salary",
        "What was your total salary, wages and employment allowances for the year?",
        "currency",
        3,
        data_path="part_c.employment.salary_wages_allowances",
        required=False,
    )

    q_bonus = get_or_create_question(
        db,
        form,
        income,
        "A_EMPLOYMENT_BONUS",
        "employment_bonus",
        "How much did you receive in employment bonuses or perquisites?",
        "currency",
        4,
        data_path="part_c.employment.bonus_perquisites",
        required=False,
    )

    q_rent = get_or_create_question(
        db,
        form,
        income,
        "A_RENTAL_INCOME",
        "rental_income",
        "How much rental income did you receive during the year?",
        "currency",
        5,
        data_path="part_c.rent_dividends_fees_royalties.rent",
        required=False,
    )

    q_dividends = get_or_create_question(
        db,
        form,
        income,
        "A_DIVIDEND_INCOME",
        "dividend_income",
        "How much dividend income did you receive?",
        "currency",
        6,
        data_path="part_c.rent_dividends_fees_royalties.dividends",
        required=False,
    )

    q_fees = get_or_create_question(
        db,
        form,
        income,
        "A_FEES_INCOME",
        "fees_income",
        "How much income did you receive from fees?",
        "currency",
        7,
        data_path="part_c.rent_dividends_fees_royalties.fees",
        required=False,
    )

    q_royalties = get_or_create_question(
        db,
        form,
        income,
        "A_ROYALTY_INCOME",
        "royalty_income",
        "How much royalty income did you receive?",
        "currency",
        8,
        data_path="part_c.rent_dividends_fees_royalties.royalties",
        required=False,
    )

    q_interest = get_or_create_question(
        db,
        form,
        income,
        "A_INTEREST_INCOME",
        "interest_income",
        "How much interest income did you receive?",
        "currency",
        9,
        data_path="part_c.interest_discounts_premiums.interest",
        required=False,
    )

    q_discount = get_or_create_question(
        db,
        form,
        income,
        "A_DISCOUNT_REBATE_INCOME",
        "discount_rebate_income",
        "How much income did you receive from discounts or rebates?",
        "currency",
        10,
        data_path="part_c.interest_discounts_premiums.discounts_rebates",
        required=False,
    )

    q_premium = get_or_create_question(
        db,
        form,
        income,
        "A_PREMIUM_INCOME",
        "premium_income",
        "How much premium income did you receive?",
        "currency",
        11,
        data_path="part_c.interest_discounts_premiums.premium",
        required=False,
    )

    q_annuity = get_or_create_question(
        db,
        form,
        income,
        "A_ANNUITY_INCOME",
        "annuity_income",
        "How much annuity income did you receive?",
        "currency",
        12,
        data_path="part_c.annuity",
        required=False,
    )

    q_asset_gain = get_or_create_question(
        db,
        form,
        income,
        "A_ASSET_DISPOSAL_GAIN",
        "asset_disposal_gain",
        "What gain did you make from disposal of assets, including property or virtual assets?",
        "currency",
        13,
        data_path="part_c.asset_disposal_gain",
        required=False,
    )

    q_prizes = get_or_create_question(
        db,
        form,
        income,
        "A_PRIZES_HONORARIA_AWARDS",
        "prizes_honoraria_awards",
        "How much did you receive from prizes, honoraria or awards?",
        "currency",
        14,
        data_path="part_c.prizes_honoraria_awards",
        required=False,
    )

    q_other_income = get_or_create_question(
        db,
        form,
        income,
        "A_OTHER_INCOME",
        "other_income",
        "Do you have any other income not already mentioned?",
        "currency",
        15,
        data_path="part_c.other_income",
        required=False,
    )

    q_has_loss_capital_allowance = get_or_create_question(
        db,
        form,
        income,
        "A_HAS_LOSS_CAPITAL_ALLOWANCE",
        "has_loss_capital_allowance",
        "Do you have any allowable loss or capital allowance to deduct?",
        "boolean",
        16,
        data_path="part_c.deductions.has_loss_capital_allowance",
        required=True,
        metadata_json={
            "conversation_role": "yes_no_gate",
        },
    )

    q_deductions_before_total = get_or_create_question(
        db,
        form,
        income,
        "A_LOSS_CAPITAL_ALLOWANCE",
        "loss_capital_allowance",
        "How much allowable loss or capital allowance should be deducted?",
        "currency",
        17,
        data_path="part_c.deductions.loss_capital_allowance",
        required=False,
    )

    # --------------------------------------------------------
    # ELIGIBLE DEDUCTIONS
    # --------------------------------------------------------

    deductions = get_or_create_section(
        db,
        form,
        "PART_C_ELIGIBLE_DEDUCTIONS",
        "Part C — Eligible Deductions",
        "INDIVIDUAL",
        3,
    )

    q_deduction_types = get_or_create_question(
        db,
        form,
        deductions,
        "A_ELIGIBLE_DEDUCTIONS",
        "eligible_deductions",
        "Which eligible deductions apply to you for this year?",
        "multi_choice",
        1,
        data_path="part_c.eligible_deductions",
        required=False,
    )

    add_options(
        db,
        q_deduction_types,
        [
            ("rent_relief", "Rent relief"),
            ("nhf", "National Housing Fund"),
            ("nhia", "National Health Insurance"),
            ("life_assurance", "Life assurance premium"),
            ("pension", "Pension"),
            ("housing_loan_interest", "Interest on a loan for developing an owner-occupied house"),
        ],
    )

    q_rent_paid = get_or_create_question(
        db,
        form,
        deductions,
        "A_ANNUAL_RENT_PAID",
        "annual_rent_paid",
        "How much annual rent did you pay?",
        "currency",
        2,
        data_path="part_c.eligible_deductions.rent_relief.annual_rent_paid",
        required=False,
    )

    q_nhf = get_or_create_question(
        db,
        form,
        deductions,
        "A_NHF_CONTRIBUTION",
        "nhf_contribution",
        "How much did you contribute to the National Housing Fund?",
        "currency",
        3,
        data_path="part_c.eligible_deductions.nhf",
        required=False,
    )

    q_nhia = get_or_create_question(
        db,
        form,
        deductions,
        "A_NHIA_CONTRIBUTION",
        "nhia_contribution",
        "How much did you contribute to National Health Insurance?",
        "currency",
        4,
        data_path="part_c.eligible_deductions.nhia",
        required=False,
    )

    q_life = get_or_create_question(
        db,
        form,
        deductions,
        "A_LIFE_ASSURANCE_PREMIUM",
        "life_assurance_premium",
        "How much did you pay in life assurance premiums?",
        "currency",
        5,
        data_path="part_c.eligible_deductions.life_assurance",
        required=False,
    )

    q_pension = get_or_create_question(
        db,
        form,
        deductions,
        "A_PENSION",
        "pension",
        "How much eligible pension contribution did you make?",
        "currency",
        6,
        data_path="part_c.eligible_deductions.pension",
        required=False,
    )

    q_housing_loan_interest = get_or_create_question(
        db,
        form,
        deductions,
        "A_HOUSING_LOAN_INTEREST",
        "housing_loan_interest",
        "How much interest did you pay on a loan for developing your owner-occupied house?",
        "currency",
        7,
        data_path="part_c.eligible_deductions.housing_loan_interest",
        required=False,
    )

    # --------------------------------------------------------
    # CALCULATED / SYSTEM VALUES
    # --------------------------------------------------------

    calculation = get_or_create_section(
        db,
        form,
        "PART_C_CALCULATIONS",
        "Part C — System Calculation Fields",
        "SYSTEM",
        4,
    )

    get_or_create_question(
        db,
        form,
        calculation,
        "A_TOTAL_INCOME",
        "total_income",
        "Total Income",
        "currency",
        1,
        data_path="part_c.total_income",
        scope="SYSTEM",
        metadata_json={
            "calculated": True,
            "authoritative_source": "CODING_UNIT",
        },
    )

    get_or_create_question(
        db,
        form,
        calculation,
        "A_CHARGEABLE_INCOME",
        "chargeable_income",
        "Chargeable Income",
        "currency",
        2,
        data_path="part_c.chargeable_income",
        scope="SYSTEM",
        metadata_json={
            "calculated": True,
            "authoritative_source": "CODING_UNIT",
        },
    )

    # --------------------------------------------------------
    # PART D — TAX
    # --------------------------------------------------------

    tax = get_or_create_section(
        db,
        form,
        "PART_D_TAX",
        "Part D — Tax Payable",
        "SYSTEM",
        5,
    )

    get_or_create_question(
        db,
        form,
        tax,
        "A_TAX_PAYABLE",
        "tax_payable",
        "Tax Payable",
        "currency",
        1,
        data_path="part_d.tax_payable",
        scope="SYSTEM",
        metadata_json={
            "calculated": True,
            "authoritative_source": "CODING_UNIT",
        },
    )

    get_or_create_question(
        db,
        form,
        tax,
        "A_TAX_CREDIT_REFUND",
        "tax_credit_refund",
        "Tax Credit or Refund",
        "currency",
        2,
        data_path="part_d.tax_credit_refund",
        scope="SYSTEM",
    )

    get_or_create_question(
        db,
        form,
        tax,
        "A_NET_TAX_DUE",
        "net_tax_due",
        "Net Tax Due",
        "currency",
        3,
        data_path="part_d.net_tax_due",
        scope="SYSTEM",
        metadata_json={
            "calculated": True,
            "authoritative_source": "CODING_UNIT",
        },
    )

    # --------------------------------------------------------
    # PART E/F — PAYMENT / REMITTANCE
    # --------------------------------------------------------

    payment = get_or_create_section(
        db,
        form,
        "PART_E_F_PAYMENT",
        "Part E/F — Payment and Remittance",
        "SYSTEM",
        6,
    )

    get_or_create_question(
        db,
        form,
        payment,
        "A_PAYMENT_EVIDENCE",
        "payment_evidence",
        "Payment evidence",
        "file",
        1,
        data_path="payment.evidence",
        scope="SYSTEM",
    )

    # --------------------------------------------------------
    # DECLARATION
    # --------------------------------------------------------

    declaration = get_or_create_section(
        db,
        form,
        "PART_F_DECLARATION",
        "Declaration",
        "INDIVIDUAL",
        7,
    )

    q_declaration = get_or_create_question(
        db,
        form,
        declaration,
        "A_DECLARATION_CONFIRMATION",
        "declaration_confirmation",
        (
            "I confirm that the information provided is true and correct "
            "to the best of my knowledge."
        ),
        "boolean",
        1,
        data_path="declaration.confirmed",
        required=True,
    )

    get_or_create_question(
        db,
        form,
        declaration,
        "A_DECLARATION_SIGNATURE",
        "signature",
        "Please provide your signature or approved electronic confirmation.",
        "signature",
        2,
        data_path="declaration.signature",
        required=True,
    )

    # --------------------------------------------------------
    # BRANCHING RULES
    # --------------------------------------------------------

    # Income source → income questions

    income_rules = [
        ("employment", q_salary),
        ("employment", q_bonus),
        ("business", q_business_income),
        ("rent", q_rent),
        ("dividends", q_dividends),
        ("fees", q_fees),
        ("royalties", q_royalties),
        ("interest", q_interest),
        ("discounts_rebates", q_discount),
        ("premium", q_premium),
        ("annuity", q_annuity),
        ("asset_disposal", q_asset_gain),
        ("prizes_awards", q_prizes),
        ("other", q_other_income),
    ]

    for source_value, target in income_rules:
        add_rule(
            db,
            form,
            q_income_sources,
            q_has_loss_capital_allowance,
            q_deductions_before_total,
            target,
            "contains",
            source_value,
            "equals",
            True,
            "SHOW",
        )

    # Deduction → amount questions

    deduction_rules = [
        ("rent_relief", q_rent_paid),
        ("nhf", q_nhf),
        ("nhia", q_nhia),
        ("life_assurance", q_life),
        ("pension", q_pension),
        ("housing_loan_interest", q_housing_loan_interest),
    ]

    for source_value, target in deduction_rules:
        add_rule(
            db,
            form,
            q_deduction_types,
            q_has_loss_capital_allowance,
            q_deductions_before_total,
            target,
            "contains",
            source_value,
            "equals",
            True,
            "SHOW",
        )

    return form


# ============================================================
# FORM H1
# ============================================================

def seed_form_h1(db):
    form = get_or_create_form(
        db,
        "FORM_H1",
        "Form H1 — Employer Return",
        "Employer return containing employer information and employee remuneration details.",
    )

    employer = get_or_create_section(
        db,
        form,
        "H1_EMPLOYER",
        "Employer Information",
        "EMPLOYER",
        1,
    )

    employer_questions = [
        ("H1_YEAR", "year", "What year are you filing for?", "number", "employer.year"),
        ("H1_REFERENCE_NUMBER", "reference_number", "What is the employer Reference Number/TIN?", "text", "employer.reference_number"),
        ("H1_EMPLOYER_NAME", "employer_name", "What is the name of the employer?", "text", "employer.name"),
        ("H1_ADDRESS", "address", "What is the employer's address?", "textarea", "employer.address"),
        ("H1_EMAIL", "email", "What is the employer's email address?", "email", "employer.email"),
    ]

    for sequence, (code, field, prompt, answer_type, path) in enumerate(
        employer_questions, start=1
    ):
        get_or_create_question(
            db,
            form,
            employer,
            code,
            field,
            prompt,
            answer_type,
            sequence,
            data_path=path,
            scope="EMPLOYER",
            required=True,
        )

    employee_count = get_or_create_question(
        db,
        form,
        employer,
        "H1_EMPLOYEE_COUNT",
        "employee_count",
        "How many employees are included in this return?",
        "number",
        6,
        data_path="employees.count",
        scope="EMPLOYER",
        required=True,
        validation_rules={"min": 1},
        metadata_json={
            "conversation_control": "repeat_group_count",
            "repeat_group_code": "employee",
        },
    )

    employee = get_or_create_section(
        db,
        form,
        "H1_EMPLOYEES",
        "Employee Details",
        "EMPLOYEE",
        2,
        repeatable=True,
        repeat_group_code="employee",
    )

    h1_employee_questions = [
        ("H1_EMPLOYEE_NAME", "name", "What is the employee's name?", "text", "name"),
        ("H1_EMPLOYEE_NATIONALITY", "nationality", "What is the employee's nationality?", "text", "nationality"),
        ("H1_EMPLOYEE_RIN", "individual_rin", "What is the employee's Individual RIN?", "text", "individual_rin"),
        ("H1_FIRST_APPOINTMENT", "date_first_appointment", "What was the employee's date of first appointment?", "date", "date_first_appointment"),
        ("H1_EMPLOYEE_GSM", "gsm", "What is the employee's GSM/phone number?", "phone", "gsm"),
        ("H1_BASIC_SALARY", "annual_basic_salary", "What is the employee's annual basic salary?", "currency", "annual_basic_salary"),
        ("H1_RENT", "rent", "What was the employee's annual rent benefit in cash or kind?", "currency", "rent_cash_kind"),
        ("H1_TRANSPORT", "transport", "What was the employee's annual transport benefit in cash or kind?", "currency", "transport_cash_kind"),
        ("H1_LEAVE_BONUS", "leave_bonus", "What was the employee's leave bonus allowance?", "currency", "leave_bonus_allowance"),
        ("H1_13TH_MONTH", "thirteenth_month", "What was the employee's 13th month salary?", "currency", "thirteenth_month_salary"),
        ("H1_OTHER_ALLOWANCES", "other_allowances", "What other allowances did the employee receive?", "currency", "other_allowances"),
        ("H1_TAX_RELIEFS", "tax_reliefs", "What were the employee's annual tax reliefs?", "currency", "annual_tax_reliefs"),
        ("H1_TAX_DEDUCTED", "tax_deducted", "How much tax was deducted from the employee during the year?", "currency", "annual_tax_deducted"),
    ]

    for sequence, (code, field, prompt, answer_type, path) in enumerate(
        h1_employee_questions, start=1
    ):
        get_or_create_question(
            db,
            form,
            employee,
            code,
            field,
            prompt,
            answer_type,
            sequence,
            data_path=f"employee.{path}",
            scope="EMPLOYEE",
            repeat_group_code="employee",
        )

    certification = get_or_create_section(
        db,
        form,
        "H1_CERTIFICATION",
        "Certification",
        "EMPLOYER",
        3,
    )

    certification_questions = [
        ("H1_DIRECTOR_NAME", "director_name", "What is the name of the Director or equivalent?", "text"),
        ("H1_DIRECTOR_DESIGNATION", "designation", "What is the Director's designation/position?", "text"),
        ("H1_CERTIFICATION_SIGNATURE", "signature", "Please provide the authorised signature.", "signature"),
        ("H1_CERTIFICATION_DATE", "date", "What is the certification date?", "date"),
    ]

    for sequence, (code, field, prompt, answer_type) in enumerate(
        certification_questions, start=1
    ):
        get_or_create_question(
            db,
            form,
            certification,
            code,
            field,
            prompt,
            answer_type,
            sequence,
            data_path=f"certification.{field}",
            scope="EMPLOYER",
        )

    return form


# ============================================================
# FORM H3
# ============================================================

def seed_form_h3(db):
    form = get_or_create_form(
        db,
        "FORM_H3",
        "Form H3 — Employer Return",
        "Employer return containing employer information and detailed employee remuneration.",
    )

    employer = get_or_create_section(
        db,
        form,
        "H3_EMPLOYER",
        "Employer Information",
        "EMPLOYER",
        1,
    )

    h3_employer_questions = [
        ("H3_EMPLOYER_NAME", "employer_name", "What is the name of the employer?", "text", "employer.name"),
        ("H3_ADDRESS", "address", "What is the employer's address?", "textarea", "employer.address"),
        ("H3_CONTACT_NUMBER", "contact_number", "What is the employer's contact number?", "phone", "employer.contact_number"),
        ("H3_BRANCH_OFFICE", "branch_office", "What branch office does this return relate to?", "text", "employer.branch_office"),
        ("H3_EMAIL", "email", "What is the employer's email address?", "email", "employer.email"),
        ("H3_COMPANY_RIN", "company_rin", "What is the Company RIN (CMP)?", "text", "employer.company_rin"),
        ("H3_BUSINESS_RIN", "business_rin", "What is the Business RIN (FOR/INF)?", "text", "employer.business_rin"),
        ("H3_ESTABLISHMENT_TAX_ID", "establishment_tax_id", "What is the Establishment Tax ID?", "text", "employer.establishment_tax_id"),
        ("H3_YEAR", "year", "What year are you filing for?", "number", "employer.year"),
    ]

    for sequence, (code, field, prompt, answer_type, path) in enumerate(
        h3_employer_questions, start=1
    ):
        get_or_create_question(
            db,
            form,
            employer,
            code,
            field,
            prompt,
            answer_type,
            sequence,
            data_path=path,
            scope="EMPLOYER",
            required=True,
        )

    employee_count = get_or_create_question(
        db,
        form,
        employer,
        "H3_EMPLOYEE_COUNT",
        "employee_count",
        "How many employees are included in this return?",
        "number",
        10,
        data_path="employees.count",
        scope="EMPLOYER",
        required=True,
        validation_rules={"min": 1},
        metadata_json={
            "conversation_control": "repeat_group_count",
            "repeat_group_code": "employee",
        },
    )

    employee = get_or_create_section(
        db,
        form,
        "H3_EMPLOYEES",
        "Employee Details",
        "EMPLOYEE",
        2,
        repeatable=True,
        repeat_group_code="employee",
    )

    h3_employee_questions = [
        ("H3_EMPLOYEE_NAME", "name", "What is the employee's name?", "text", "name"),
        ("H3_EMPLOYEE_NATIONALITY", "nationality", "What is the employee's nationality?", "text", "nationality"),
        ("H3_EMPLOYEE_TAX_ID", "individual_tax_id", "What is the employee's Individual Tax ID?", "text", "individual_tax_id"),
        ("H3_DESIGNATION", "designation", "What is the employee's designation/position?", "text", "designation"),
        ("H3_EMPLOYEE_PHONE", "phone", "What is the employee's individual phone number?", "phone", "phone"),
        ("H3_BASIC_SALARY", "annual_basic_salary", "What is the employee's annual basic salary?", "currency", "annual_basic_salary"),
        ("H3_RENT", "rent", "What was the employee's annual rent benefit in cash or kind?", "currency", "rent_cash_kind"),
        ("H3_TRANSPORT", "transport", "What was the employee's annual transport benefit in cash or kind?", "currency", "transport_cash_kind"),
        ("H3_LEAVE_BONUS", "leave_bonus", "What was the employee's leave bonus allowance?", "currency", "leave_bonus_allowance"),
        ("H3_13TH_MONTH", "thirteenth_month", "What was the employee's 13th month salary?", "currency", "thirteenth_month_salary"),
        ("H3_OTHER_ALLOWANCES", "other_allowances", "What other allowances did the employee receive?", "currency", "other_allowances"),
        ("H3_TOTAL_ALLOWANCES", "total_allowances", "What is the employee's total allowances?", "currency", "total_allowances"),
        ("H3_BIK", "benefit_in_kind", "What was the employee's benefit in kind?", "currency", "benefit_in_kind"),
        ("H3_TOTAL_SALARY_ALLOWANCES", "total_salary_allowances", "What is the employee's total salary and allowances?", "currency", "total_salary_allowances"),
    ]

    for sequence, (code, field, prompt, answer_type, path) in enumerate(
        h3_employee_questions, start=1
    ):
        get_or_create_question(
            db,
            form,
            employee,
            code,
            field,
            prompt,
            answer_type,
            sequence,
            data_path=f"employee.{path}",
            scope="EMPLOYEE",
            repeat_group_code="employee",
        )

    certification = get_or_create_section(
        db,
        form,
        "H3_CERTIFICATION",
        "Certification",
        "EMPLOYER",
        3,
    )

    certification_questions = [
        ("H3_DIRECTOR_NAME", "director_name", "What is the name of the Director or equivalent?", "text"),
        ("H3_DIRECTOR_DESIGNATION", "designation", "What is the Director's designation/position?", "text"),
        ("H3_CERTIFICATION_SIGNATURE", "signature", "Please provide the authorised signature.", "signature"),
        ("H3_CERTIFICATION_DATE", "date", "What is the certification date?", "date"),
    ]

    for sequence, (code, field, prompt, answer_type) in enumerate(
        certification_questions, start=1
    ):
        get_or_create_question(
            db,
            form,
            certification,
            code,
            field,
            prompt,
            answer_type,
            sequence,
            data_path=f"certification.{field}",
            scope="EMPLOYER",
        )

    return form


# ============================================================
# MAIN
# ============================================================

def main():
    db = SessionLocal()

    try:
        print("Seeding EIRS form definitions...")

        form_a = seed_form_a(db)
        form_h1 = seed_form_h1(db)
        form_h3 = seed_form_h3(db)

        db.commit()

        print()
        print("Form seeding completed successfully.")
        print()
        print(f"FORM_A  id={form_a.id}")
        print(f"FORM_H1 id={form_h1.id}")
        print(f"FORM_H3 id={form_h3.id}")
        print()

        for form in [form_a, form_h1, form_h3]:
            sections = (
                db.query(FormSection)
                .filter(FormSection.form_id == form.id)
                .count()
            )

            questions = (
                db.query(Question)
                .filter(Question.form_id == form.id)
                .count()
            )

            rules = (
                db.query(QuestionRule)
                .filter(QuestionRule.form_id == form.id)
                .count()
            )

            print(
                f"{form.code}: "
                f"{sections} sections, "
                f"{questions} questions, "
                f"{rules} rules"
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()