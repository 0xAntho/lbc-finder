from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Request, HTTPException
from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_DAYS, ALLOWED_PHONES


def _normalize(phone: str) -> str:
    clean = phone.strip().replace(" ", "").replace("-", "").replace("+", "").replace(".", "")
    if clean.startswith("33") and len(clean) == 11:
        clean = "0" + clean[2:]
    return clean


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
        raise HTTPException(status_code=401, detail="Not authenticated")
    phone = verify_token(token)
    if not phone:
        raise HTTPException(status_code=401, detail="Expired session")
    return phone


def check_phone(phone: str) -> str | None:
    normalized = _normalize(phone)
    if normalized in ALLOWED_PHONES:
        return normalized
    return None