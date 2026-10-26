from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class TaxpayerCreate(BaseModel):
    full_name: str
    phone_number: str
    whatsapp_number: str | None = None
    email: EmailStr | None = None
    occupation: str | None = None
    address: str | None = None
    city: str | None = None
    state: str = "Edo"


class TaxpayerOut(BaseModel):
    id: int
    taxpayer_reference: str
    full_name: str
    phone_number: str
    whatsapp_number: str | None
    email: EmailStr | None
    occupation: str | None
    address: str | None
    city: str | None
    state: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)