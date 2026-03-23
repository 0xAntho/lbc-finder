import logging
import threading
from contextlib import asynccontextmanager
import time
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import init_db, get_db, User, Alert, Listing
from app.auth import create_token, get_current_user, check_phone, verify_token
from app.scheduler import start_scheduler, stop_scheduler, run_all_alerts, check_alert
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(5):
        try:
            init_db()
            break
        except Exception as e:
            logger.warning(f"DB non prête, tentative {attempt+1}/5 : {e}")
            time.sleep(3)
    else:
        logger.error("Impossible de connecter la DB après 5 tentatives")
        raise RuntimeError("DB connection failed")
    start_scheduler()
    logger.info("Application démarrée")
    yield
    stop_scheduler()
    logger.info("Application arrêtée")


app = FastAPI(title="Sa Maison", lifespan=lifespan)


# ── Pydantic models ───────────────────────────────────────────────────────

class LoginBody(BaseModel):
    phone: str

class AlertBody(BaseModel):
    name: str
    city: str
    lat: float
    lng: float
    radius_km: int
    max_price: Optional[int] = None
    min_surface: Optional[int] = None
    min_land_surface: Optional[int] = None
    min_outside_surface: Optional[int] = None
    min_rooms: Optional[int] = None

class RunNowBody(BaseModel):
    phone: str


# ── Helpers ───────────────────────────────────────────────────────────────

def get_or_create_user(db: Session, phone: str) -> User:
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        user = User(phone_number=phone)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ── Health check (keep-alive Railway) ────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    token = request.cookies.get("session")
    if token and verify_token(token):
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
async def login(body: LoginBody, db: Session = Depends(get_db)):
    if not check_phone(body.phone):
        return JSONResponse({"error": "Numéro non autorisé."}, status_code=401)

    clean = body.phone.strip().replace(" ", "").replace("-", "").replace(".", "")
    get_or_create_user(db, clean)
    token = create_token(clean)

    resp = JSONResponse({"redirect": "/dashboard"})
    resp.set_cookie("session", token, httponly=True, max_age=60 * 60 * 24 * 30)
    return resp


@app.post("/logout")
async def logout():
    resp = JSONResponse({"redirect": "/login"})
    resp.delete_cookie("session")
    return resp


# ── Dashboard ─────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    message: str = None,
    error: str = None,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        return RedirectResponse(url="/login")
    alerts = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).all()
    return templates.TemplateResponse(request, "dashboard.html", {"alerts": alerts})


# ── Alertes CRUD ──────────────────────────────────────────────────────────

@app.get("/alerts/new", response_class=HTMLResponse)
async def new_alert_page(request: Request, phone: str = Depends(get_current_user)):
    return templates.TemplateResponse(request, "alert_form.html", {"alert": None})


@app.post("/alerts/new")
async def create_alert(
    body: AlertBody,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        return JSONResponse({"error": "Non autorisé"}, status_code=401)

    alert = Alert(
        user_id=user.id,
        name=body.name,
        city=body.city,
        lat=body.lat,
        lng=body.lng,
        radius_km=body.radius_km,
        max_price=body.max_price,
        min_surface=body.min_surface,
        min_land_surface=body.min_land_surface,
        min_outside_surface=body.min_outside_surface,
        min_rooms=body.min_rooms,
    )
    db.add(alert)
    db.commit()
    return JSONResponse({"redirect": "/dashboard"})


@app.get("/alerts/{alert_id}/edit", response_class=HTMLResponse)
async def edit_alert_page(
    request: Request,
    alert_id: int,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if not alert:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request, "alert_form.html", {"alert": alert})


@app.post("/alerts/{alert_id}/edit")
async def update_alert(
    alert_id: int,
    body: AlertBody,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if not alert:
        return JSONResponse({"error": "Alerte introuvable"}, status_code=404)

    alert.name = body.name
    alert.city = body.city
    alert.lat = body.lat
    alert.lng = body.lng
    alert.radius_km = body.radius_km
    alert.max_price = body.max_price
    alert.min_surface = body.min_surface
    alert.min_land_surface = body.min_land_surface
    alert.min_outside_surface = body.min_outside_surface
    alert.min_rooms = body.min_rooms
    db.commit()
    return JSONResponse({"redirect": "/dashboard"})


@app.post("/alerts/{alert_id}/toggle")
async def toggle_alert(
    alert_id: int,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if alert:
        alert.is_active = not alert.is_active
        db.commit()
    return JSONResponse({"redirect": "/dashboard"})


@app.post("/alerts/{alert_id}/delete")
async def delete_alert(
    alert_id: int,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if alert:
        db.query(Listing).filter(Listing.alert_id == alert_id).delete()
        db.delete(alert)
        db.commit()
    return JSONResponse({"redirect": "/dashboard"})


# ── Historique ────────────────────────────────────────────────────────────

@app.get("/history", response_class=HTMLResponse)
async def history(
    request: Request,
    alert_id: int = None,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    alerts = db.query(Alert).filter(Alert.user_id == user.id).all()

    query = db.query(Listing).join(Alert).filter(Alert.user_id == user.id)
    selected_alert = None
    if alert_id:
        query = query.filter(Listing.alert_id == alert_id)
        selected_alert = db.query(Alert).filter(Alert.id == alert_id).first()

    listings = query.order_by(Listing.created_at.desc()).limit(200).all()
    return templates.TemplateResponse(request, "history.html", {"listings": listings, "alerts": alerts, "selected_alert": selected_alert, "active": "history"})


# ── API utilitaires ───────────────────────────────────────────────────────

@app.post("/api/run-now")
async def run_now(body: RunNowBody):
    if not check_phone(body.phone):
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    threading.Thread(target=run_all_alerts, daemon=True).start()
    return JSONResponse({"status": "started"})


@app.post("/api/alerts/{alert_id}/check")
async def check_now(alert_id: int, body: RunNowBody):
    if not check_phone(body.phone):
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    threading.Thread(target=check_alert, args=(alert_id,), daemon=True).start()
    return JSONResponse({"status": "started", "alert_id": alert_id})