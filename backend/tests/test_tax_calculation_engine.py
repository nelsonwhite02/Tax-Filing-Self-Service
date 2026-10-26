
from decimal import Decimal

from app.services.tax_calculation_engine import (EIRSTaxCalculationEngine, normalize_form_answers)

engine = EIRSTaxCalculationEngine()


def test_form_a_zero_income():
    result = engine.calculate_form_a({}, tax_year=2026)
    assert result.total_income == Decimal("0.00")
    assert result.chargeable_income == Decimal("0.00")
    assert result.tax_payable == Decimal("0.00")
    assert result.net_tax_due == Decimal("0.00")


def test_form_a_rent_relief_cap():
    result = engine.calculate_form_a(
        {
            "business_income": 10_000_000,
            "annual_rent_paid": 4_000_000,
        },
        tax_year=2026,
    )
    # 20% of 4m = 800k, capped at 500k.
    assert result.details["deductions"]["rent_relief"] == Decimal("500000.00")
    assert result.chargeable_income == Decimal("9_500_000.00")


def test_form_a_progressive_bands():
    result = engine.calculate_form_a(
        {"business_income": 10_000_000},
        tax_year=2026,
    )
    # 0 on first 800k
    # 15% of 2.2m = 330k
    # 18% of remaining 7m = 1.26m
    assert result.tax_payable == Decimal("1_590_000.00")


def test_form_a_credit_cannot_make_net_tax_negative():
    result = engine.calculate_form_a(
        {
            "business_income": 2_000_000,
            "tax_credit_refund": 999_999,
        },
        tax_year=2026,
    )
    assert result.net_tax_due == Decimal("0.00")


def test_normalize_seeded_form_a_codes():
    normalized = normalize_form_answers(
        {
            "A_BUSINESS_INCOME": 5_000_000,
            "A_ANNUAL_RENT_PAID": 1_000_000,
            "A_PENSION": 100_000,
        }
    )
    assert normalized == {
        "business_income": 5_000_000,
        "annual_rent_paid": 1_000_000,
        "pension": 100_000,
    }


def test_h1_employee():
    result = engine.calculate_employee(
        {
            "name": "Employee One",
            "annual_basic_salary": 2_000_000,
            "rent_cash_kind": 200_000,
            "transport_cash_kind": 100_000,
            "leave_bonus_allowance": 100_000,
            "thirteenth_month_salary": 0,
            "other_allowances": 100_000,
            "annual_tax_reliefs": 100_000,
            "annual_tax_deducted": 50_000,
        },
        tax_year=2026,
        form_code="FORM_H1",
    )
    assert result.total_income == Decimal("2_500_000.00")
    assert result.chargeable_income == Decimal("2_400_000.00")
    # First 800k = 0; next 1.6m @15% = 240k.
    assert result.tax_payable == Decimal("240_000.00")
    assert result.net_tax_due == Decimal("190_000.00")


def test_h3_bik_is_included():
    result = engine.calculate_employee(
        {
            "name": "Employee Two",
            "annual_basic_salary": 1_000_000,
            "benefit_in_kind": 500_000,
        },
        tax_year=2026,
        form_code="FORM_H3",
    )
    assert result.total_income == Decimal("1_500_000.00")
    assert result.chargeable_income == Decimal("1_500_000.00")
    assert result.tax_payable == Decimal("105_000.00")


def test_employer_aggregate():
    result = engine.calculate_employer_return(
        [
            {"name": "A", "annual_basic_salary": 1_000_000},
            {"name": "B", "annual_basic_salary": 2_000_000},
        ],
        tax_year=2026,
        form_code="FORM_H3",
    )
    assert result["employee_count"] == 2
    assert result["tax_payable"] == 210_000.0
