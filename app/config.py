import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

_db_url = os.getenv("DATABASE_URL", "sqlite:///./leboncoin_alert.db")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)

def _normalize(phone: str) -> str:
    return phone.strip().replace(" ", "").replace("-", "").replace(".", "").replace("+", "")

_raw_phones   = [p.strip() for p in os.getenv("PHONE_NUMBER", "").split(",") if p.strip()]
_raw_wa_phones = [p.strip() for p in os.getenv("WHATSAPP_PHONE", "").split(",") if p.strip()]
_raw_wa_keys   = [p.strip() for p in os.getenv("WHATSAPP_APIKEY", "").split(",") if p.strip()]

WHATSAPP_CREDENTIALS: dict[str, tuple[str, str]] = {
    _normalize(phone): (wa_phone, wa_key)
    for phone, wa_phone, wa_key in zip(_raw_phones, _raw_wa_phones, _raw_wa_keys)
}

ALLOWED_PHONES: set[str] = set(WHATSAPP_CREDENTIALS.keys())