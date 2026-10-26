import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.taxpayer import Taxpayer
from app.schemas.taxpayer import TaxpayerCreate, TaxpayerOut


router = APIRouter(
    prefix="/api/taxpayers",
    tags=["Taxpayers"],
)


@router.post(
    "/",
    response_model=TaxpayerOut,
    status_code=201,
)
def create_taxpayer(
    taxpayer_data: TaxpayerCreate,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Taxpayer)
        .filter(
            Taxpayer.phone_number
            == taxpayer_data.phone_number
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A taxpayer with this phone number already exists.",
        )

    taxpayer = Taxpayer(
        taxpayer_reference=(
            f"EIRS-{uuid.uuid4().hex[:12].upper()}"
        ),
        **taxpayer_data.model_dump(),
    )

    db.add(taxpayer)
    db.commit()
    db.refresh(taxpayer)

    return taxpayer


@router.get(
    "/{taxpayer_id}",
    response_model=TaxpayerOut,
)
def get_taxpayer(
    taxpayer_id: int,
    db: Session = Depends(get_db),
):
    taxpayer = (
        db.query(Taxpayer)
        .filter(Taxpayer.id == taxpayer_id)
        .first()
    )

    if not taxpayer:
        raise HTTPException(
            status_code=404,
            detail="Taxpayer not found.",
        )

    return taxpayer