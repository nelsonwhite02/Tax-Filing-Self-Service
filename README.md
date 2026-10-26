# EIRS Form Definition / Question Engine Starter

This bundle adds the database layer for FORM_A, FORM_H1 and FORM_H3.

## Files
- `models/form_definition.py` — FormDefinition, FormSection, Question, QuestionOption, QuestionRule
- `models/__init__.py` — imports for the new models (merge these into the existing app/models/__init__.py; do not replace your existing User/Taxpayer imports)
- `scripts/seed_forms.py` — seeds the three form definitions and the fields from the supplied forms

## Apply to C:\EIRS_Tax_System\backend

1. Copy `models/form_definition.py` to `backend/app/models/form_definition.py`.
2. Merge the four imports from `models/__init__.py` into the existing `backend/app/models/__init__.py`, keeping the existing User and Taxpayer imports.
3. Copy `scripts/seed_forms.py` to `backend/scripts/seed_forms.py` and create an empty `backend/scripts/__init__.py` if it does not exist.
4. Update Alembic `env.py` so the new models are imported through `app.models` before `target_metadata = Base.metadata`.
5. From `backend` run:
   `alembic revision --autogenerate -m "add configurable form definitions and question engine"`
6. Inspect the migration. It should create exactly five new tables:
   - form_definitions
   - form_sections
   - questions
   - question_options
   - question_rules
7. Apply it:
   `alembic upgrade head`
8. Seed:
   `python -m scripts.seed_forms`

## Important
The seed data reflects the fields visible in the supplied Form A, H1 and H3 forms. It deliberately does not invent official coding-unit rules or tax calculations. Calculated H3 totals are marked as calculated metadata rather than authoritative tax calculations.
