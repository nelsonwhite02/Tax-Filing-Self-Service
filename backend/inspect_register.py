from app.core.database import SessionLocal
from app.models import BusinessRegister

db = SessionLocal()
try:
    rows = db.query(BusinessRegister).filter(
        BusinessRegister.is_active.is_(True)
    ).order_by(BusinessRegister.id).limit(10).all()

    print("\n--- Active business register records ---")
    for b in rows:
        print({
            "id": b.id,
            "business_name": b.business_name,
            "normalized_name": b.normalized_name,
            "registration_number": b.registration_number,
            "tax_identifier": b.tax_identifier,
            "phone_number": b.phone_number,
            "email": b.email,
            "matched_taxpayer_id": b.matched_taxpayer_id,
        })
finally:
    db.close()
