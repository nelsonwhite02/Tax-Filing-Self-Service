from pathlib import Path
import re
import shutil

path = Path("app/routers/business_register.py")
if not path.exists():
    raise SystemExit(f"STOP: File not found: {path.resolve()}")

source = path.read_text(encoding="utf-8")
updated = source

# Fix the incorrect taxpayer lookup inside get_business().
start = updated.find("def get_business(")
if start < 0:
    raise SystemExit("STOP: Could not find get_business(). No changes written.")

next_route = updated.find("\n@router.", start + 1)
end = next_route if next_route >= 0 else len(updated)
section = updated[start:end]

wrong_lookup = re.compile(
    r"db\.query\(Taxpayer\)\s*\.first\(\)"
)
section_fixed, count = wrong_lookup.subn(
    "db.query(Taxpayer).filter("
    "Taxpayer.id == business.matched_taxpayer_id"
    ").first()",
    section,
    count=1,
)

if count != 1:
    raise SystemExit(
        "STOP: The expected incorrect taxpayer lookup was not found "
        "inside get_business(). No changes written."
    )

updated = updated[:start] + section_fixed + updated[end:]

# Add request-model imports only when needed.
if "from pydantic import BaseModel" not in updated:
    import_anchor = "from sqlalchemy.orm import Session"
    if import_anchor not in updated:
        raise SystemExit("STOP: Could not locate the import section.")
    updated = updated.replace(
        import_anchor,
        "from pydantic import BaseModel\n" + import_anchor,
        1,
    )

if "from typing import Optional" not in updated:
    import_anchor = "from sqlalchemy.orm import Session"
    updated = updated.replace(
        import_anchor,
        "from typing import Optional\n" + import_anchor,
        1,
    )

# Add the review request model before the router declaration.
if "class BusinessMatchReviewRequest" not in updated:
    router_anchor = "router = APIRouter("
    if router_anchor not in updated:
        raise SystemExit("STOP: Could not locate router declaration.")
    request_model = '''class BusinessMatchReviewRequest(BaseModel):
    action: str
    taxpayer_id: Optional[int] = None
    review_notes: Optional[str] = None


'''
    updated = updated.replace(
        router_anchor, request_model + router_anchor, 1
    )

# Add an explicit admin review endpoint. Never auto-confirm matches.
endpoint_marker = '@router.post("/{business_id}/match-review")'
if endpoint_marker not in updated:
    endpoint = '''

@router.post("/{business_id}/match-review")
def review_business_match(
    business_id: int,
    payload: BusinessMatchReviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    action = (payload.action or "").strip().upper()

    if action not in {"CONFIRM", "REJECT"}:
        raise HTTPException(
            status_code=422,
            detail="action must be CONFIRM or REJECT.",
        )

    business = (
        db.query(BusinessRegister)
        .filter(BusinessRegister.id == business_id)
        .first()
    )
    if not business:
        raise HTTPException(status_code=404, detail="Business not found.")

    matched_taxpayer = None

    if action == "CONFIRM":
        if payload.taxpayer_id is None:
            raise HTTPException(
                status_code=422,
                detail="taxpayer_id is required when confirming a match.",
            )

        matched_taxpayer = (
            db.query(Taxpayer)
            .filter(Taxpayer.id == payload.taxpayer_id)
            .first()
        )
        if not matched_taxpayer:
            raise HTTPException(
                status_code=404,
                detail="Taxpayer not found.",
            )

        business.matched_taxpayer_id = matched_taxpayer.id
        business.match_status = "CONFIRMED"
        # Keep the existing algorithmic confidence score unchanged.
        # Identity confirmation does NOT verify an official tax filing.

    else:
        # An explicit admin rejection clears the current taxpayer link.
        business.matched_taxpayer_id = None
        business.match_confidence = None
        business.match_status = "REJECTED"
        matched_taxpayer = None

    if payload.review_notes is not None:
        business.review_notes = payload.review_notes.strip() or None

    try:
        db.commit()
        db.refresh(business)
    except Exception:
        db.rollback()
        raise

    result = serialize_business(business)
    result["matched_taxpayer"] = (
        {
            "id": matched_taxpayer.id,
            "taxpayer_reference": matched_taxpayer.taxpayer_reference,
            "full_name": matched_taxpayer.full_name,
        }
        if matched_taxpayer
        else None
    )
    return result
'''
    updated = updated.rstrip() + "\n" + endpoint

# Make a backup before writing any changes.
backup = path.with_name("business_register.py.pre_match_review.bak")
if not backup.exists():
    shutil.copy2(path, backup)

path.write_text(updated, encoding="utf-8")
print("Patch applied.")
print(f"Backup: {backup.resolve()}")
print("Next: run the syntax check below.")
