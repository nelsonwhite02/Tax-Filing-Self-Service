
import re
import unicodedata
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import (
    Answer,
    BusinessRegister,
    Conversation,
    FormDefinition,
    Question,
    TaxAssessment,
    Taxpayer,
)


POTENTIAL_NON_FILER_LABEL = (
    "No matching completed filing found — verification required"
)


def normalize_text(value):
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"[^\w]+", " ", value).strip()


def normalize_identifier(value):
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def normalize_phone(value):
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def normalize_email(value):
    return (str(value).strip().casefold() if value is not None else "")


def answer_values(value):
    """Extract comparable scalar values from JSON answers."""
    if value is None:
        return []

    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        text = str(value).strip()
        return [text] if text else []

    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(answer_values(item))
        return result

    if isinstance(value, dict):
        result = []
        for key in ("value", "answer", "text", "name", "phone", "email"):
            if key in value:
                result.extend(answer_values(value[key]))
        return result

    return []


def question_category(question):
    """Identify the kind of value an answer field is likely to contain."""
    text = " ".join(
        str(value or "")
        for value in (
            question.code,
            question.field_name,
            question.prompt,
        )
    ).casefold()

    # Specific identifiers must be checked before generic names.
    if any(term in text for term in (
        "tax_id", "tax_identifier", "tax identification",
        "tax identification number", "tin", "taxpayer identification",
    )):
        return "tax_id"

    if any(term in text for term in (
        "registration_number", "registration number",
        "business registration", "rc_number", "rc number",
        "cac number",
    )):
        return "registration"

    if any(term in text for term in (
        "email", "e-mail",
    )):
        return "email"

    if any(term in text for term in (
        "phone", "telephone", "mobile", "whatsapp",
        "contact_number", "contact number",
    )):
        return "phone"

    if any(term in text for term in (
        "business_name", "business name",
        "company_name", "company name",
        "employer_name", "employer name",
        "registered_name", "registered name",
        "trading_name", "trading name",
    )):
        return "business_name"

    if any(term in text for term in (
        "full_name", "full name", "taxpayer_name",
        "taxpayer name", "individual_name", "individual name",
        "applicant_name", "applicant name",
        "proprietor_name", "proprietor name",
        "contact_person", "contact person",
    )):
        return "person_name"

    return None


def compare_values(category, left, right):
    """Compare two values using category-appropriate normalization."""
    if category in ("tax_id", "registration"):
        a, b = normalize_identifier(left), normalize_identifier(right)
    elif category == "phone":
        a, b = normalize_phone(left), normalize_phone(right)
        # Avoid treating very short numbers as reliable identifiers.
        if len(a) < 7 or len(b) < 7:
            return False
        # Allow common international/national formatting differences.
        if a == b:
            return True
        return a.lstrip("0") == b.lstrip("0")
    elif category == "email":
        a, b = normalize_email(left), normalize_email(right)
    else:
        a, b = normalize_text(left), normalize_text(right)

    return bool(a and b and a == b)


def build_reconciliation(db: Session, tax_year=None, limit=50, offset=0):
    business_query = db.query(BusinessRegister).filter(
        BusinessRegister.is_active.is_(True)
    )

    if tax_year is not None:
        business_query = business_query.filter(
            (BusinessRegister.tax_year == tax_year)
            | (BusinessRegister.tax_year.is_(None))
        )

    total = business_query.count()
    businesses = (
        business_query
        .order_by(BusinessRegister.business_name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    taxpayers = db.query(Taxpayer).filter(
        Taxpayer.is_active.is_(True)
    ).all()

    # Load supported forms and their saved answers.
    answer_rows = (
        db.query(
            Answer,
            Question,
            FormDefinition.code.label("form_code"),
            Conversation.taxpayer_id,
            Conversation.status.label("conversation_status"),
        )
        .join(Question, Answer.question_id == Question.id)
        .join(Conversation, Answer.conversation_id == Conversation.id)
        .join(FormDefinition, Question.form_id == FormDefinition.id)
        .filter(
            Conversation.form_id == FormDefinition.id,
            FormDefinition.code.in_(("FORM_A", "FORM_H1", "FORM_H3")),
        )
        .all()
    )

    answers_by_taxpayer = defaultdict(list)
    answer_counts = defaultdict(int)

    for answer, question, form_code, taxpayer_id, status in answer_rows:
        values = answer_values(answer.value_json)

        answers_by_taxpayer[taxpayer_id].append({
            "form_code": form_code,
            "question_code": question.code,
            "category": question_category(question),
            "values": values,
            "conversation_id": answer.conversation_id,
            "conversation_status": (status or "").upper(),
        })
        answer_counts[form_code] += 1

    conversations = (
        db.query(
            Conversation.id,
            Conversation.taxpayer_id,
            Conversation.status,
            FormDefinition.code.label("form_code"),
        )
        .join(FormDefinition, Conversation.form_id == FormDefinition.id)
        .filter(FormDefinition.code.in_(("FORM_A", "FORM_H1", "FORM_H3")))
        .all()
    )

    conversations_by_taxpayer = defaultdict(list)
    conversation_by_id = {}

    for conversation in conversations:
        record = {
            "conversation_id": conversation.id,
            "taxpayer_id": conversation.taxpayer_id,
            "status": (conversation.status or "").upper(),
            "form_code": conversation.form_code,
        }
        conversations_by_taxpayer[conversation.taxpayer_id].append(record)
        conversation_by_id[conversation.id] = record

    assessments = db.query(TaxAssessment).all()
    assessments_by_conversation = defaultdict(list)

    for assessment in assessments:
        if assessment.conversation_id is not None:
            assessments_by_conversation[assessment.conversation_id].append(
                assessment
            )

    # A previously saved match is retained as an existing decision.
    taxpayers_by_id = {taxpayer.id: taxpayer for taxpayer in taxpayers}

    results = []
    h1_h3_available = (
        answer_counts["FORM_H1"] > 0 or answer_counts["FORM_H3"] > 0
    )

    for business in businesses:
        target_year = (
            business.tax_year
            if business.tax_year is not None
            else tax_year
        )

        business_values = {
            "tax_id": [business.tax_identifier],
            "registration": [business.registration_number],
            "phone": [business.phone_number],
            "email": [business.email],
            "business_name": [
                business.normalized_name or business.business_name
            ],
            "person_name": [],
        }

        # Add an existing register match to the candidate set first.
        candidates_by_id = {}

        saved_id = business.matched_taxpayer_id
        if saved_id is not None and saved_id in taxpayers_by_id:
            saved_taxpayer = taxpayers_by_id[saved_id]
            try:
                saved_score = (
                    round(float(business.match_confidence))
                    if business.match_confidence is not None
                    else 0
                )
            except (TypeError, ValueError):
                saved_score = 0

            candidates_by_id[saved_id] = {
                "taxpayer_id": saved_id,
                "taxpayer_reference": saved_taxpayer.taxpayer_reference,
                "confidence_score": max(0, min(100, saved_score)),
                "reasons": ["Previously saved taxpayer match"],
                "review_required": (
                    (business.match_status or "").upper()
                    not in ("CONFIRMED", "VERIFIED")
                ),
                "saved_match": True,
            }

        for taxpayer in taxpayers:
            reasons = []
            score = 0

            # Match direct taxpayer profile fields.
            profile_fields = {
                "phone": [
                    taxpayer.phone_number,
                    taxpayer.whatsapp_number,
                ],
                "email": [taxpayer.email],
                "person_name": [taxpayer.full_name],
            }

            for category, profile_values in profile_fields.items():
                for register_value in business_values[category]:
                    if not register_value:
                        continue
                    if any(
                        compare_values(category, register_value, value)
                        for value in profile_values
                        if value
                    ):
                        if category == "phone":
                            score = max(score, 85)
                            reasons.append("Taxpayer phone number match")
                        elif category == "email":
                            score = max(score, 85)
                            reasons.append("Taxpayer email match")
                        else:
                            score = max(score, 45)
                            reasons.append("Taxpayer name match")

            # Compare the register with relevant saved form answers.
            for answer in answers_by_taxpayer.get(taxpayer.id, []):
                category = answer["category"]
                if not category:
                    continue

                for register_value in business_values.get(category, []):
                    if not register_value:
                        continue

                    if any(
                        compare_values(category, register_value, value)
                        for value in answer["values"]
                    ):
                        if category in ("tax_id", "registration"):
                            score = max(score, 100)
                            reasons.append(
                                "Tax or registration identifier matches saved form answer"
                            )
                        elif category in ("phone", "email"):
                            score = max(score, 85)
                            reasons.append(
                                f"{category.replace('_', ' ').title()} matches saved form answer"
                            )
                        elif category == "business_name":
                            score = max(score, 80)
                            reasons.append(
                                "Business name matches saved form answer"
                            )
                        else:
                            score = max(score, 60)
                            reasons.append(
                                "Personal name matches saved form answer"
                            )

            if score:
                # Remove duplicate reasons while retaining order.
                reasons = list(dict.fromkeys(reasons))
                candidates_by_id[taxpayer.id] = {
                    "taxpayer_id": taxpayer.id,
                    "taxpayer_reference": taxpayer.taxpayer_reference,
                    "confidence_score": score,
                    "reasons": reasons,
                    "review_required": score < 80,
                    "saved_match": False,
                }

        candidates = sorted(
            candidates_by_id.values(),
            key=lambda item: (
                item["confidence_score"],
                not item["review_required"],
            ),
            reverse=True,
        )

        # Keep the full set long enough to detect ambiguous top matches.
        if len(candidates) > 1:
            top_score = candidates[0]["confidence_score"]
            second_score = candidates[1]["confidence_score"]
            if top_score == second_score:
                candidates[0]["review_required"] = True
                candidates[1]["review_required"] = True

        candidates = candidates[:5]

        completed_interactions = []
        assessment_evidence = []

        for candidate in candidates:
            taxpayer_id = candidate["taxpayer_id"]

            for conversation in conversations_by_taxpayer.get(
                taxpayer_id, []
            ):
                if conversation["status"] != "COMPLETED":
                    continue

                # When a year is requested, require an assessment linked to
                # this conversation and that specific year. The conversation
                # model itself has no tax-year field.
                linked_assessments = assessments_by_conversation.get(
                    conversation["conversation_id"], []
                )

                if target_year is not None:
                    year_assessments = [
                        assessment
                        for assessment in linked_assessments
                        if assessment.tax_year == target_year
                    ]
                    if not year_assessments:
                        continue

                completed_interactions.append({
                    "taxpayer_id": taxpayer_id,
                    "conversation_id": conversation["conversation_id"],
                    "form_code": conversation["form_code"],
                    "evidence_type": (
                        f"Completed {conversation['form_code']} conversation"
                    ),
                    "tax_year": target_year,
                    "confirmation": (
                        "Completed chatbot interaction matched; verify "
                        "official filing records where required"
                    ),
                })

            for linked_assessments in assessments_by_conversation.values():
                for assessment in linked_assessments:
                    if assessment.taxpayer_id != taxpayer_id:
                        continue
                    if (
                        target_year is not None
                        and assessment.tax_year != target_year
                    ):
                        continue

                    assessment_evidence.append({
                        "taxpayer_id": taxpayer_id,
                        "assessment_id": assessment.id,
                        "form_code": assessment.form_code,
                        "tax_year": assessment.tax_year,
                        "calculation_status": assessment.calculation_status,
                        "evidence_type": (
                            "Linked assessment record; not independently "
                            "proof of official filing"
                        ),
                    })

        # Remove duplicate evidence rows.
        unique_interactions = {
            (
                item["taxpayer_id"],
                item["conversation_id"],
                item["form_code"],
            ): item
            for item in completed_interactions
        }
        completed_interactions = list(unique_interactions.values())

        unique_assessments = {
            item["assessment_id"]: item for item in assessment_evidence
        }
        assessment_evidence = list(unique_assessments.values())

        # Only a unique, sufficiently strong match with a completed
        # conversation counts as a matched filing interaction.
        top_candidate = candidates[0] if candidates else None
        ambiguous_top_match = (
            len(candidates) > 1
            and candidates[0]["confidence_score"]
            == candidates[1]["confidence_score"]
        )

        matched_completed = False
        if top_candidate and not ambiguous_top_match:
            matched_completed = any(
                item["taxpayer_id"] == top_candidate["taxpayer_id"]
                for item in completed_interactions
            )

        if matched_completed:
            filing_label = "Matched completed filing interaction"
        elif candidates:
            filing_label = (
                "Matching taxpayer found — no qualifying completed filing "
                "interaction found"
            )
        else:
            filing_label = POTENTIAL_NON_FILER_LABEL

        results.append({
            "business": {
                "id": business.id,
                "business_name": business.business_name,
                "registration_number": business.registration_number,
                "tax_year": business.tax_year,
                "city": business.city,
                "source_name": business.source_name,
                "source_url": business.source_url,
            },
            "requested_tax_year": target_year,
            "candidate_matches": candidates,
            "filing_review": {
                "status_label": filing_label,
                "completed_form_a_interactions": [
                    item for item in completed_interactions
                    if item["form_code"] == "FORM_A"
                ],
                "completed_employer_interactions": [
                    item for item in completed_interactions
                    if item["form_code"] in ("FORM_H1", "FORM_H3")
                ],
                "assessment_records": assessment_evidence,
                "h1_h3_evidence_status": (
                    "Saved H1/H3 answers exist; review the matched employer "
                    "and completed conversation"
                    if h1_h3_available
                    else "No saved H1/H3 answers were found"
                ),
                "verification_required": True,
                "notice": (
                    "A match identifies a possible corresponding chatbot "
                    "record. A completed interaction is not independently "
                    "proof of official tax filing. Verify official records "
                    "where required."
                ),
            },
            "review_required": (
                not candidates
                or ambiguous_top_match
                or any(item["review_required"] for item in candidates)
                or not matched_completed
            ),
        })

    return {
        "total_businesses": total,
        "limit": limit,
        "offset": offset,
        "tax_year_filter": tax_year,
        "read_only": True,
        "h1_h3_answer_count": (
            answer_counts["FORM_H1"] + answer_counts["FORM_H3"]
        ),
        "h1_h3_evidence_available": h1_h3_available,
        "items": results,
    }
