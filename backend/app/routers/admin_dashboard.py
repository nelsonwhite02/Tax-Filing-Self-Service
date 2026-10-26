from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Answer, Conversation, FormDefinition, Question, TaxAssessment, Taxpayer, User


router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard"])
bearer = HTTPBearer()
password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"


class AdminLogin(BaseModel):
    email: str
    password: str


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired admin session.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id = int(payload.get("sub", ""))
    except (JWTError, TypeError, ValueError):
        raise unauthorized

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or (user.role or "").lower() != "admin":
        raise unauthorized

    return user


def answer_value(answer):
    value = answer.value_json
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def money(value):
    return float(value or Decimal("0"))


def assessment_dict(a):
    return {
        "id": a.id,
        "taxpayer_id": a.taxpayer_id,
        "conversation_id": a.conversation_id,
        "filing_type": a.filing_type,
        "form_code": a.form_code,
        "tax_year": a.tax_year,
        "total_income": money(a.total_income),
        "total_deductions": money(a.total_deductions),
        "chargeable_income": money(a.chargeable_income),
        "tax_payable": money(a.tax_payable),
        "tax_credit": money(a.tax_credit),
        "net_tax_due": money(a.net_tax_due),
        "calculation_status": a.calculation_status,
        "calculation_version": a.calculation_version,
        "created_at": a.created_at,
        "presented_at": a.presented_at,
        "accepted_at": getattr(a, "accepted_at", None),
        "objected_at": a.objected_at,
        "paid_at": a.paid_at,
    }


def taxpayer_dict(t):
    return {
        "id": t.id,
        "taxpayer_reference": t.taxpayer_reference,
        "full_name": t.full_name,
        "phone_number": t.phone_number,
        "whatsapp_number": t.whatsapp_number,
        "email": t.email,
        "occupation": t.occupation,
        "address": t.address,
        "city": t.city,
        "state": getattr(t, "state", None),
        "is_active": t.is_active,
        "created_at": t.created_at,
    }


@router.post("/login")
def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )

    if (
        not user
        or not user.is_active
        or (user.role or "").lower() != "admin"
        or not password_context.verify(data.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    expires = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token = jwt.encode(
        {"sub": str(user.id), "exp": expires, "role": "admin"},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires,
        "admin": {"id": user.id, "full_name": user.full_name, "email": user.email},
    }


@router.get("/me")
def admin_me(
    user: User = Depends(require_admin),
):
    return {"id": user.id, "full_name": user.full_name, "email": user.email, "role": user.role}


@router.get("/dashboard/overview")
def dashboard_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    taxpayers = db.query(func.count(Taxpayer.id)).scalar() or 0
    conversations = db.query(func.count(Conversation.id)).scalar() or 0
    completed = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.status == "COMPLETED")
        .scalar() or 0
    )
    assessments = db.query(func.count(TaxAssessment.id)).scalar() or 0

    by_type = {}
    for filing_type in ("FORM_A", "FORM_H1", "FORM_H3"):
        rows = db.query(TaxAssessment).filter(
            TaxAssessment.filing_type == filing_type
        )
        by_type[filing_type] = {
            "count": rows.count(),
            "net_tax_due": money(
                db.query(func.coalesce(func.sum(TaxAssessment.net_tax_due), 0))
                .filter(TaxAssessment.filing_type == filing_type)
                .scalar()
            ),
        }

    return {
        "taxpayers": taxpayers,
        "conversations": conversations,
        "completed_conversations": completed,
        "assessments": assessments,
        "by_filing_type": by_type,
    }


@router.get("/dashboard/assessments")
def list_assessments(
    filing_type: str | None = Query(default=None),
    tax_year: int | None = Query(default=None, ge=2000, le=2200),
    search: str | None = Query(default=None, max_length=150),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = (
        db.query(TaxAssessment, Taxpayer)
        .join(Taxpayer, Taxpayer.id == TaxAssessment.taxpayer_id)
    )

    if filing_type:
        if filing_type not in {"FORM_A", "FORM_H1", "FORM_H3"}:
            raise HTTPException(status_code=400, detail="Unsupported filing type.")
        query = query.filter(TaxAssessment.filing_type == filing_type)

    if tax_year is not None:
        query = query.filter(TaxAssessment.tax_year == tax_year)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            Taxpayer.full_name.ilike(term),
            Taxpayer.taxpayer_reference.ilike(term),
            Taxpayer.phone_number.ilike(term),
            TaxAssessment.form_code.ilike(term),
        ))

    total = query.count()
    rows = (
        query.order_by(TaxAssessment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [
            {
                **assessment_dict(a),
                "taxpayer": {
                    "id": t.id,
                    "taxpayer_reference": t.taxpayer_reference,
                    "full_name": t.full_name,
                    "phone_number": t.phone_number,
                    "occupation": t.occupation,
                    "city": t.city,
                },
            }
            for a, t in rows
        ],
    }


@router.get("/dashboard/individuals")
def list_individuals(
    search: str | None = Query(default=None, max_length=150),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = (
        db.query(Taxpayer)
        .join(TaxAssessment, TaxAssessment.taxpayer_id == Taxpayer.id)
        .filter(TaxAssessment.filing_type == "FORM_A")
        .distinct()
    )

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            Taxpayer.full_name.ilike(term),
            Taxpayer.taxpayer_reference.ilike(term),
            Taxpayer.phone_number.ilike(term),
        ))

    taxpayers = query.order_by(Taxpayer.full_name.asc()).limit(500).all()
    result = []

    for t in taxpayers:
        assessments = (
            db.query(TaxAssessment)
            .filter(
                TaxAssessment.taxpayer_id == t.id,
                TaxAssessment.filing_type == "FORM_A",
            )
            .order_by(TaxAssessment.tax_year.desc())
            .all()
        )
        item = taxpayer_dict(t)
        item["assessment_count"] = len(assessments)
        item["latest_tax_year"] = assessments[0].tax_year if assessments else None
        item["assessments"] = [assessment_dict(a) for a in assessments]
        result.append(item)

    return {"total": len(result), "items": result}


@router.get("/dashboard/employers")
def list_employers(
    search: str | None = Query(default=None, max_length=150),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = (
        db.query(Answer, Question, Conversation, Taxpayer, FormDefinition)
        .join(Question, Question.id == Answer.question_id)
        .join(Conversation, Conversation.id == Answer.conversation_id)
        .join(Taxpayer, Taxpayer.id == Conversation.taxpayer_id)
        .join(FormDefinition, FormDefinition.id == Conversation.form_id)
        .filter(
            FormDefinition.code.in_(["FORM_H1", "FORM_H3"]),
            Question.field_name == "employer_name",
        )
        .order_by(Answer.created_at.desc())
        .limit(5000)
        .all()
    )

    employers = {}

    for answer, question, conversation, taxpayer, form in rows:
        name = answer_value(answer)
        if not isinstance(name, str) or not name.strip():
            continue

        display_name = name.strip()
        key = display_name.casefold()
        if search and search.strip().casefold() not in key:
            continue

        if key not in employers:
            employers[key] = {
                "employer_name": display_name,
                "filings": [],
                "taxpayer_contacts": [],
                "tax_years": [],
            }

        filing = {
            "conversation_id": conversation.id,
            "taxpayer_id": taxpayer.id,
            "taxpayer_name": taxpayer.full_name,
            "form_code": form.code,
            "conversation_status": conversation.status,
            "channel": conversation.channel,
            "started_at": conversation.started_at,
        }

        assessment = (
            db.query(TaxAssessment)
            .filter(TaxAssessment.conversation_id == conversation.id)
            .first()
        )
        if assessment:
            filing["assessment"] = assessment_dict(assessment)
            if assessment.tax_year not in employers[key]["tax_years"]:
                employers[key]["tax_years"].append(assessment.tax_year)

        employers[key]["filings"].append(filing)

        contact = {
            "taxpayer_id": taxpayer.id,
            "name": taxpayer.full_name,
            "phone_number": taxpayer.phone_number,
        }
        if contact not in employers[key]["taxpayer_contacts"]:
            employers[key]["taxpayer_contacts"].append(contact)

    items = sorted(employers.values(), key=lambda e: e["employer_name"].casefold())
    for item in items:
        item["tax_years"].sort(reverse=True)
        item["filing_count"] = len(item["filings"])

    return {"total": len(items), "items": items}


@router.get("/dashboard/taxpayers/{taxpayer_id}")
def taxpayer_detail(
    taxpayer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    taxpayer = db.query(Taxpayer).filter(Taxpayer.id == taxpayer_id).first()
    if not taxpayer:
        raise HTTPException(status_code=404, detail="Taxpayer not found.")

    assessments = (
        db.query(TaxAssessment)
        .filter(TaxAssessment.taxpayer_id == taxpayer_id)
        .order_by(TaxAssessment.tax_year.desc(), TaxAssessment.created_at.desc())
        .all()
    )
    conversations = (
        db.query(Conversation)
        .filter(Conversation.taxpayer_id == taxpayer_id)
        .order_by(Conversation.started_at.desc())
        .all()
    )

    return {
        "taxpayer": taxpayer_dict(taxpayer),
        "assessments": [assessment_dict(a) for a in assessments],
        "conversations": [
            {
                "id": c.id,
                "form_code": c.form.code if c.form else None,
                "status": c.status,
                "channel": c.channel,
                "started_at": c.started_at,
                "last_activity_at": c.last_activity_at,
                "completed_at": c.completed_at,
                "answer_count": len(c.answers),
            }
            for c in conversations
        ],
    }


@router.get("/dashboard/conversations/{conversation_id}")
def conversation_transcript(
    conversation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    answers = (
        db.query(Answer, Question)
        .join(Question, Question.id == Answer.question_id)
        .filter(Answer.conversation_id == conversation_id)
        .order_by(Answer.sequence.asc(), Answer.id.asc())
        .all()
    )

    return {
        "conversation": {
            "id": conversation.id,
            "taxpayer": taxpayer_dict(conversation.taxpayer),
            "form_code": conversation.form.code if conversation.form else None,
            "status": conversation.status,
            "channel": conversation.channel,
            "started_at": conversation.started_at,
            "last_activity_at": conversation.last_activity_at,
            "completed_at": conversation.completed_at,
        },
        "transcript": [
            {
                "answer_id": answer.id,
                "question_code": question.code,
                "question": question.prompt,
                "section": question.section.title if question.section else None,
                "answer": answer_value(answer),
                "raw_text": answer.raw_text,
                "transcription": answer.transcription,
                "input_type": answer.input_type,
                "repeat_group_code": answer.repeat_group_code,
                "repeat_instance": answer.repeat_instance,
                "created_at": answer.created_at,
            }
            for answer, question in answers
        ],
    }

