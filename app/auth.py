from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Request, HTTPException
from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_DAYS, PHONE_NUMBER


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
    """Vérifie que le numéro correspond à l'utilisateur autorisé."""
    # Normalise : supprime espaces, tirets, +
    clean = phone.strip().replace(" ", "").replace("-", "").replace("+", "").replace(".", "")
    allowed = PHONE_NUMBER.strip().replace(" ", "").replace("+", "")
    return clean == allowed or clean == f"33{allowed[1:]}" if allowed.startswith("0") else clean == allowed