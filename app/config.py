import os
from dotenv import load_dotenv

load_dotenv()

_raw = os.getenv("PHONE_NUMBERS") or os.getenv("PHONE_NUMBER", "")
PHONE_NUMBERS: list[str] = [p.strip() for p in _raw.split(",") if p.strip()]

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "")

_db_url = os.getenv("DATABASE_URL", "sqlite:///./leboncoin_alert.db")
DATABASE_URL = _db_url.replace("postgres://", "postgresql://", 1)