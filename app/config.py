import os
from dotenv import load_dotenv

load_dotenv()

PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./leboncoin_alert.db")