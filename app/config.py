import os
from dotenv import load_dotenv

load_dotenv()

PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "whatsapp")  # "whatsapp", "free" ou "ovh"

# Callmebot WhatsApp
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")   # format international : +33612345678
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "")

# OVH
OVH_APP_KEY = os.getenv("OVH_APP_KEY", "")
OVH_APP_SECRET = os.getenv("OVH_APP_SECRET", "")
OVH_CONSUMER_KEY = os.getenv("OVH_CONSUMER_KEY", "")
OVH_SMS_SERVICE = os.getenv("OVH_SMS_SERVICE", "")
OVH_SENDER = os.getenv("OVH_SENDER", "AlertLBC")
OVH_RECIPIENT = os.getenv("OVH_RECIPIENT", "")

# Free Mobile
FREE_USER = os.getenv("FREE_USER", "")
FREE_PASS = os.getenv("FREE_PASS", "")

DATABASE_URL = "sqlite:///./leboncoin_alert.db"