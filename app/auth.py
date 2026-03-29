from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Request, HTTPException
from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_DAYS, PHONE_NUMBERS


def _normalize(phone: str) -> str:
    return phone.strip().replace(" ", "").replace("-", "").replace("+", "").replace(".", "")


def create_token(phone: str) -> str:
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": phone, "exp": expire},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user(request: Request) -> str:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    phone = verify_token(token)
    if not phone:
        raise HTTPException(status_code=401, detail="Session expirée")
    return phone


def check_phone(phone: str) -> bool:
    clean = _normalize(phone)
    for allowed in PHONE_NUMBERS:
        a = _normalize(allowed)
        if clean == a:
            return True
        if a.startswith("0") and clean == f"33{a[1:]}":
            return True
        if clean.startswith("0") and a == f"33{clean[1:]}":
            return True
    return False