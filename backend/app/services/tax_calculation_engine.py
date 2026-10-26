
"""
EIRS Tax Calculation Engine
===========================

Authoritative, deterministic calculation layer for the EIRS taxpayer system.

This module is intentionally independent of WhatsApp, FastAPI and SQLAlchemy.
It accepts normalized tax inputs and returns a fully traceable calculation
result. The caller can persist the result to the assessment/return tables.

Implemented from the EIRS Form A / H1 / H3 fields already established in the
project.

FORM A
------
Income:
    business
    employment salary
    employment bonus
    rental
    dividend
    fees
    royalty
    interest
    discount/rebate
    premium
    annuity
    asset disposal gain
    prizes/honoraria/awards
    other income
    loss/capital allowance

Eligible deductions:
    rent relief = 20% of annual rent paid, capped at N500,000
    NHF
    NHIA
    life assurance
    pension
    housing-loan interest

Tax bands configured from the supplied Form A:
    first N800,000       0%
    next N2,200,000     15%
    next N9,000,000      18%
    next N13,000,000     21%
    next N25,000,000     23%
    above N50,000,000    25%

H1/H3
------
The employee fields from the supplied forms are normalized into annual
employment income. Employee tax is calculated progressively using the same
configured bands. H1 annual tax reliefs and H3-provided applicable deductions
are accepted as deduction inputs. Annual tax already deducted is treated as
a credit against the calculated tax.

IMPORTANT:
The rates and deduction rules are configuration, not AI-generated arithmetic.
Changing tax law must be handled by changing/versioning the rule profile and
its calculation_version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


MONEY = Decimal("0.01")


def D(value: Any) -> Decimal:
    """Convert a user/database value safely to Decimal."""
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid monetary amount.")
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("₦", "").strip()
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"Invalid monetary amount: {value!r}") from exc


def money(value: Any) -> Decimal:
    return D(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def nonnegative(value: Any, field_name: str) -> Decimal:
    amount = money(value)
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return amount


@dataclass(frozen=True)
class TaxBand:
    name: str
    width: Decimal | None
    rate: Decimal


# The profile is deliberately immutable at runtime.
FORM_A_NTA_2025_BANDS: tuple[TaxBand, ...] = (
    TaxBand("First ₦800,000", D("800000"), D("0")),
    TaxBand("Next ₦2,200,000", D("2200000"), D("0.15")),
    TaxBand("Next ₦9,000,000", D("9000000"), D("0.18")),
    TaxBand("Next ₦13,000,000", D("13000000"), D("0.21")),
    TaxBand("Next ₦25,000,000", D("25000000"), D("0.23")),
    TaxBand("Above ₦50,000,000", None, D("0.25")),
)


@dataclass(frozen=True)
class TaxRuleProfile:
    code: str = "EIRS_FORM_A_NTA_2025_V1"
    bands: tuple[TaxBand, ...] = FORM_A_NTA_2025_BANDS
    rent_relief_rate: Decimal = D("0.20")
    rent_relief_cap: Decimal = D("500000")


@dataclass
class BandBreakdown:
    band: str
    taxable_amount: Decimal
    rate: Decimal
    tax: Decimal


@dataclass
class CalculationResult:
    filing_type: str
    tax_year: int
    calculation_version: str

    total_income: Decimal
    loss_or_capital_allowance: Decimal
    gross_deductions: Decimal
    chargeable_income: Decimal

    tax_payable: Decimal
    tax_credit: Decimal
    net_tax_due: Decimal

    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        def dec(v: Decimal) -> float:
            return float(money(v))

        return {
            "filing_type": self.filing_type,
            "tax_year": self.tax_year,
            "calculation_version": self.calculation_version,
            "total_income": dec(self.total_income),
            "loss_or_capital_allowance": dec(self.loss_or_capital_allowance),
            "total_deductions": dec(self.gross_deductions),
            "chargeable_income": dec(self.chargeable_income),
            "tax_payable": dec(self.tax_payable),
            "tax_credit": dec(self.tax_credit),
            "net_tax_due": dec(self.net_tax_due),
            "details": _serialize(self.details),
        }


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(money(value))
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, BandBreakdown):
        return {
            "band": value.band,
            "taxable_amount": float(money(value.taxable_amount)),
            "rate": float(value.rate),
            "tax": float(money(value.tax)),
        }
    return value


def progressive_tax(
    taxable_income: Decimal,
    bands: Iterable[TaxBand],
) -> tuple[Decimal, list[BandBreakdown]]:
    """Apply progressive bands without rounding intermediate amounts."""
    income = nonnegative(taxable_income, "taxable_income")
    remaining = income
    total = Decimal("0")
    breakdown: list[BandBreakdown] = []

    for band in bands:
        if remaining <= 0:
            break

        if band.width is None:
            slice_amount = remaining
        else:
            slice_amount = min(remaining, band.width)

        tax = slice_amount * band.rate
        breakdown.append(
            BandBreakdown(
                band=band.name,
                taxable_amount=slice_amount,
                rate=band.rate,
                tax=tax,
            )
        )
        total += tax
        remaining -= slice_amount

    return money(total), breakdown


class EIRSTaxCalculationEngine:
    """
    Single authoritative calculator for taxpayer filings.

    The engine never reads Answer rows directly. A service layer should first
    normalize Answer.value_json into one of the input dictionaries below.
    """

    FORM_A_INCOME_FIELDS = (
        "business_income",
        "employment_salary",
        "employment_bonus",
        "rental_income",
        "dividend_income",
        "fees_income",
        "royalty_income",
        "interest_income",
        "discount_rebate_income",
        "premium_income",
        "annuity_income",
        "asset_disposal_gain",
        "prizes_honoria_awards",
        "other_income",
    )

    FORM_A_DEDUCTION_FIELDS = (
        "nhf_contribution",
        "nhia_contribution",
        "life_assurance_premium",
        "pension",
        "housing_loan_interest",
    )

    def __init__(self, profile: TaxRuleProfile | None = None):
        self.profile = profile or TaxRuleProfile()

    # ------------------------------------------------------------------
    # FORM A
    # ------------------------------------------------------------------

    def calculate_form_a(
        self,
        data: Mapping[str, Any],
        *,
        tax_year: int,
    ) -> CalculationResult:
        income = {
            key: nonnegative(data.get(key, 0), key)
            for key in self.FORM_A_INCOME_FIELDS
        }

        loss = nonnegative(
            data.get("loss_capital_allowance", 0),
            "loss_capital_allowance",
        )

        total_before_loss = sum(income.values(), Decimal("0"))
        total_income = max(Decimal("0"), total_before_loss - loss)

        annual_rent = nonnegative(
            data.get("annual_rent_paid", 0),
            "annual_rent_paid",
        )
        rent_relief = min(
            annual_rent * self.profile.rent_relief_rate,
            self.profile.rent_relief_cap,
        )

        deductions = {
            "rent_relief": rent_relief,
            "nhf_contribution": nonnegative(
                data.get("nhf_contribution", 0), "nhf_contribution"
            ),
            "nhia_contribution": nonnegative(
                data.get("nhia_contribution", 0), "nhia_contribution"
            ),
            "life_assurance_premium": nonnegative(
                data.get("life_assurance_premium", 0),
                "life_assurance_premium",
            ),
            "pension": nonnegative(data.get("pension", 0), "pension"),
            "housing_loan_interest": nonnegative(
                data.get("housing_loan_interest", 0),
                "housing_loan_interest",
            ),
        }

        gross_deductions = sum(deductions.values(), Decimal("0"))
        chargeable_income = max(
            Decimal("0"),
            total_income - gross_deductions,
        )

        tax_payable, bands = progressive_tax(
            chargeable_income,
            self.profile.bands,
        )

        tax_credit = nonnegative(
            data.get("tax_credit_refund", 0),
            "tax_credit_refund",
        )
        net_tax_due = max(Decimal("0"), tax_payable - tax_credit)

        return CalculationResult(
            filing_type="FORM_A",
            tax_year=tax_year,
            calculation_version=self.profile.code,
            total_income=money(total_income),
            loss_or_capital_allowance=money(loss),
            gross_deductions=money(gross_deductions),
            chargeable_income=money(chargeable_income),
            tax_payable=money(tax_payable),
            tax_credit=money(tax_credit),
            net_tax_due=money(net_tax_due),
            details={
                "income_components": income,
                "income_before_loss": total_before_loss,
                "deductions": deductions,
                "tax_bands": bands,
                "rules": {
                    "rent_relief_rate": self.profile.rent_relief_rate,
                    "rent_relief_cap": self.profile.rent_relief_cap,
                },
            },
        )

    # ------------------------------------------------------------------
    # H1 / H3
    # ------------------------------------------------------------------

    def calculate_employee(
        self,
        employee: Mapping[str, Any],
        *,
        tax_year: int,
        form_code: str,
    ) -> CalculationResult:
        """
        Calculate one employee's annual PAYE liability.

        H1:
            basic + rent + transport + leave + 13th month + other allowances.

        H3:
            basic + rent + transport + leave + 13th month + other allowances
            + benefit in kind.

        If H3 supplies total_salary_allowances, it is used only when component
        fields are absent, preventing double counting.
        """
        form = form_code.upper()
        if form not in {"FORM_H1", "FORM_H3"}:
            raise ValueError("Employee calculation requires FORM_H1 or FORM_H3.")

        component_keys = (
            "annual_basic_salary",
            "rent_cash_kind",
            "transport_cash_kind",
            "leave_bonus_allowance",
            "thirteenth_month_salary",
            "other_allowances",
        )

        components = {
            key: nonnegative(employee.get(key, 0), key)
            for key in component_keys
        }

        supplied_total = nonnegative(
            employee.get("total_salary_allowances", 0),
            "total_salary_allowances",
        )

        component_total = sum(components.values(), Decimal("0"))

        if component_total == 0 and supplied_total > 0:
            employment_income = supplied_total
        else:
            employment_income = component_total

        bik = Decimal("0")
        if form == "FORM_H3":
            bik = nonnegative(
                employee.get("benefit_in_kind", 0),
                "benefit_in_kind",
            )

        gross_income = employment_income + bik

        # H1 has an explicit "Annual Tax Reliefs" field.
        # H3 does not expose the same field, but the engine accepts a normalized
        # annual_tax_reliefs value if an authorized upstream source provides it.
        tax_reliefs = nonnegative(
            employee.get("annual_tax_reliefs", 0),
            "annual_tax_reliefs",
        )

        # Optional normalized statutory deductions. They are only included when
        # explicitly supplied by the upstream normalized return.
        deductions = {
            "annual_tax_reliefs": tax_reliefs,
            "nhf_contribution": nonnegative(
                employee.get("nhf_contribution", 0),
                "nhf_contribution",
            ),
            "nhia_contribution": nonnegative(
                employee.get("nhia_contribution", 0),
                "nhia_contribution",
            ),
            "life_assurance_premium": nonnegative(
                employee.get("life_assurance_premium", 0),
                "life_assurance_premium",
            ),
            "pension": nonnegative(
                employee.get("pension", 0),
                "pension",
            ),
            "housing_loan_interest": nonnegative(
                employee.get("housing_loan_interest", 0),
                "housing_loan_interest",
            ),
        }

        total_deductions = sum(deductions.values(), Decimal("0"))
        chargeable_income = max(
            Decimal("0"),
            gross_income - total_deductions,
        )

        tax_payable, bands = progressive_tax(
            chargeable_income,
            self.profile.bands,
        )

        tax_deducted = nonnegative(
            employee.get("annual_tax_deducted", 0),
            "annual_tax_deducted",
        )
        net_tax_due = max(Decimal("0"), tax_payable - tax_deducted)

        return CalculationResult(
            filing_type=form,
            tax_year=tax_year,
            calculation_version=self.profile.code,
            total_income=money(gross_income),
            loss_or_capital_allowance=Decimal("0.00"),
            gross_deductions=money(total_deductions),
            chargeable_income=money(chargeable_income),
            tax_payable=money(tax_payable),
            tax_credit=money(tax_deducted),
            net_tax_due=money(net_tax_due),
            details={
                "employee": {
                    "name": employee.get("name"),
                    "designation": employee.get("designation"),
                    "individual_tax_id": employee.get(
                        "individual_tax_id", employee.get("tax_id")
                    ),
                },
                "income_components": components,
                "benefit_in_kind": bik,
                "deductions": deductions,
                "tax_bands": bands,
                "annual_tax_deducted": tax_deducted,
            },
        )

    def calculate_employer_return(
        self,
        employees: Iterable[Mapping[str, Any]],
        *,
        tax_year: int,
        form_code: str,
    ) -> dict[str, Any]:
        """
        Calculate all employees in an H1/H3 return.

        The employer's PAYE liability is the sum of employee tax payable.
        The balance still due is the sum of employee net tax due after
        annual tax already deducted.
        """
        results: list[CalculationResult] = []

        for employee in employees:
            results.append(
                self.calculate_employee(
                    employee,
                    tax_year=tax_year,
                    form_code=form_code,
                )
            )

        total_income = sum(
            (r.total_income for r in results), Decimal("0")
        )
        total_deductions = sum(
            (r.gross_deductions for r in results), Decimal("0")
        )
        total_tax = sum(
            (r.tax_payable for r in results), Decimal("0")
        )
        total_credit = sum(
            (r.tax_credit for r in results), Decimal("0")
        )
        net_due = sum(
            (r.net_tax_due for r in results), Decimal("0")
        )

        return {
            "filing_type": form_code.upper(),
            "tax_year": tax_year,
            "calculation_version": self.profile.code,
            "employee_count": len(results),
            "total_income": money(total_income),
            "total_deductions": money(total_deductions),
            "chargeable_income": money(
                max(Decimal("0"), total_income - total_deductions)
            ),
            "tax_payable": money(total_tax),
            "tax_credit": money(total_credit),
            "net_tax_due": money(net_due),
            "employees": [r.as_dict() for r in results],
        }


def normalize_form_answers(answers: Mapping[str, Any]) -> dict[str, Any]:
    """
    Convert the exact seeded Form A field names into engine input names.

    The service layer should call this after collecting Answer.value_json.
    No question text or WhatsApp wording is used by the calculator.
    """
    aliases = {
        "A_BUSINESS_INCOME": "business_income",
        "A_EMPLOYMENT_SALARY": "employment_salary",
        "A_EMPLOYMENT_BONUS": "employment_bonus",
        "A_RENTAL_INCOME": "rental_income",
        "A_DIVIDEND_INCOME": "dividend_income",
        "A_FEES_INCOME": "fees_income",
        "A_ROYALTY_INCOME": "royalty_income",
        "A_INTEREST_INCOME": "interest_income",
        "A_DISCOUNT_REBATE_INCOME": "discount_rebate_income",
        "A_PREMIUM_INCOME": "premium_income",
        "A_ANNUITY_INCOME": "annuity_income",
        "A_ASSET_DISPOSAL_GAIN": "asset_disposal_gain",
        "A_PRIZES_HONORIA_AWARDS": "prizes_honoria_awards",
        "A_OTHER_INCOME": "other_income",
        "A_LOSS_CAPITAL_ALLOWANCE": "loss_capital_allowance",
        "A_ANNUAL_RENT_PAID": "annual_rent_paid",
        "A_NHF_CONTRIBUTION": "nhf_contribution",
        "A_NHIA_CONTRIBUTION": "nhia_contribution",
        "A_LIFE_ASSURANCE_PREMIUM": "life_assurance_premium",
        "A_PENSION": "pension",
        "A_HOUSING_LOAN_INTEREST": "housing_loan_interest",
        "A_TAX_CREDIT_REFUND": "tax_credit_refund",
    }

    normalized: dict[str, Any] = {}
    for key, target in aliases.items():
        if key in answers:
            normalized[target] = answers[key]

    return normalized
