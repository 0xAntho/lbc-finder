import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import init_db, get_db, User, Alert, Listing
from app.auth import create_token, get_current_user, check_phone
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
    init_db()
    start_scheduler()
    logger.info("Application démarrée")
    yield
    stop_scheduler()
    logger.info("Application arrêtée")


app = FastAPI(title="AlertLBC", lifespan=lifespan)


# ── Helpers ──────────────────────────────────────────────────────────────

def get_or_create_user(db: Session, phone: str) -> User:
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        user = User(phone_number=phone)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ── Auth ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    token = request.cookies.get("session")
    if token:
        from app.auth import verify_token
        if verify_token(token):
            return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    response: Response,
    phone: str = Form(...),
    db: Session = Depends(get_db),
):
    if not check_phone(phone):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Numéro non autorisé."},
        )

    # Normaliser le numéro
    clean = phone.strip().replace(" ", "").replace("-", "").replace(".", "")
    get_or_create_user(db, clean)
    token = create_token(clean)

    resp = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie("session", token, httponly=True, max_age=60 * 60 * 24 * 30)
    return resp


@app.post("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=303)
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
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "alerts": alerts, "active": "dashboard", "message": message, "error": error},
    )


# ── Alertes CRUD ──────────────────────────────────────────────────────────

@app.get("/alerts/new", response_class=HTMLResponse)
async def new_alert_page(
    request: Request,
    phone: str = Depends(get_current_user),
):
    return templates.TemplateResponse("alert_form.html", {"request": request, "alert": None})


@app.post("/alerts/new")
async def create_alert(
    request: Request,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    name: str = Form(...),
    city: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    radius_km: int = Form(...),
    max_price: str = Form(""),
    min_surface: str = Form(""),
    min_land_surface: str = Form(""),
    min_outside_surface: str = Form(""),
    min_rooms: str = Form(""),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user:
        return RedirectResponse(url="/login")

    def to_int(v): return int(v) if v and v.strip() else None

    alert = Alert(
        user_id=user.id,
        name=name,
        city=city,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        max_price=to_int(max_price),
        min_surface=to_int(min_surface),
        min_land_surface=to_int(min_land_surface),
        min_outside_surface=to_int(min_outside_surface),
        min_rooms=to_int(min_rooms),
    )
    db.add(alert)
    db.commit()
    return RedirectResponse(url="/dashboard?message=Alerte créée avec succès", status_code=303)


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
    return templates.TemplateResponse("alert_form.html", {"request": request, "alert": alert})


@app.post("/alerts/{alert_id}/edit")
async def update_alert(
    alert_id: int,
    phone: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    name: str = Form(...),
    city: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    radius_km: int = Form(...),
    max_price: str = Form(""),
    min_surface: str = Form(""),
    min_land_surface: str = Form(""),
    min_outside_surface: str = Form(""),
    min_rooms: str = Form(""),
):
    user = db.query(User).filter(User.phone_number == phone).first()
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if not alert:
        return RedirectResponse(url="/dashboard")

    def to_int(v): return int(v) if v and v.strip() else None

    alert.name = name
    alert.city = city
    alert.lat = lat
    alert.lng = lng
    alert.radius_km = radius_km
    alert.max_price = to_int(max_price)
    alert.min_surface = to_int(min_surface)
    alert.min_land_surface = to_int(min_land_surface)
    alert.min_outside_surface = to_int(min_outside_surface)
    alert.min_rooms = to_int(min_rooms)
    db.commit()
    return RedirectResponse(url="/dashboard?message=Alerte mise à jour", status_code=303)


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
    return RedirectResponse(url="/dashboard", status_code=303)


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
    return RedirectResponse(url="/dashboard?message=Alerte supprimée", status_code=303)


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

    query = (
        db.query(Listing)
        .join(Alert)
        .filter(Alert.user_id == user.id)
    )
    selected_alert = None
    if alert_id:
        query = query.filter(Listing.alert_id == alert_id)
        selected_alert = db.query(Alert).filter(Alert.id == alert_id).first()

    listings = query.order_by(Listing.created_at.desc()).limit(200).all()
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "listings": listings,
            "alerts": alerts,
            "selected_alert": selected_alert,
            "active": "history",
        },
    )


# ── API utilitaires ───────────────────────────────────────────────────────

@app.post("/api/run-now")
async def run_now(phone: str = Depends(get_current_user)):
    """Déclenche le job immédiatement (pour tests)."""
    import threading
    threading.Thread(target=run_all_alerts, daemon=True).start()
    return {"status": "started"}


@app.post("/api/alerts/{alert_id}/check")
async def check_now(
    alert_id: int,
    phone: str = Depends(get_current_user),
):
    """Vérifie une alerte spécifique immédiatement."""
    import threading
    threading.Thread(target=check_alert, args=(alert_id,), daemon=True).start()
    return {"status": "started", "alert_id": alert_id}