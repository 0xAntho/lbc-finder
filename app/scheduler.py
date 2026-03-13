import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal, Listing
from app.sms import send_sms

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _get_ad_attribute(ad, *keys):
    """Récupère un attribut dans les attributes[] de l'annonce lbc."""
    attrs = getattr(ad, "attributes", []) or []
    for attr in attrs:
        if hasattr(attr, "key") and attr.key in keys:
            try:
                return int(attr.value)
            except (ValueError, TypeError):
                return attr.value
    return None


def check_alert(alert_id: int):
    """Vérifie une alerte et notifie pour les nouvelles annonces."""
    db = SessionLocal()
    try:
        # Import ici pour éviter les circular imports au démarrage
        from app.database import Alert
        import lbc

        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert or not alert.is_active:
            return

        logger.info(f"Vérification alerte #{alert.id} — {alert.name}")

        client = lbc.Client()
        location = lbc.City(
            lat=alert.lat,
            lng=alert.lng,
            radius=alert.radius_km * 1000,
            city=alert.city,
        )

        kwargs = {
            "locations": [location],
            "sort": lbc.Sort.NEWEST,
            "ad_type": lbc.AdType.OFFER,
            "category": lbc.Category.IMMOBILIER,
            "limit": 50,
            "page": 1,
        }

        if alert.max_price:
            kwargs["price"] = [0, alert.max_price]
        if alert.min_surface:
            kwargs["square"] = [alert.min_surface, 99999]
        if alert.min_rooms:
            kwargs["rooms"] = [alert.min_rooms, 99]

        try:
            result = client.search(**kwargs)
        except Exception as e:
            logger.error(f"Erreur API lbc pour alerte #{alert.id}: {e}")
            alert.last_checked_at = datetime.utcnow()
            db.commit()
            return

        new_count = 0
        for ad in result.ads:
            lbc_id = str(ad.list_id)

            # Vérifier si déjà en base
            existing = db.query(Listing).filter(Listing.leboncoin_id == lbc_id).first()
            if existing:
                continue

            # Extraire les surfaces depuis les attributs
            land_surface = _get_ad_attribute(ad, "land_surface", "square_land")
            outside_surface = _get_ad_attribute(ad, "outside_surface", "square_outside")
            surface = _get_ad_attribute(ad, "square") or getattr(ad, "surface", None)
            rooms = _get_ad_attribute(ad, "rooms") or getattr(ad, "rooms", None)

            # Post-filtrage surface terrain
            if alert.min_land_surface and land_surface:
                if land_surface < alert.min_land_surface:
                    continue

            # Post-filtrage surface extérieure
            if alert.min_outside_surface and outside_surface:
                if outside_surface < alert.min_outside_surface:
                    continue

            # Extraire prix et ville
            price = None
            if hasattr(ad, "price") and ad.price:
                try:
                    price = int(ad.price[0]) if isinstance(ad.price, list) else int(ad.price)
                except (ValueError, TypeError, IndexError):
                    pass

            city = None
            if hasattr(ad, "location") and ad.location:
                city = getattr(ad.location, "city_label", None) or getattr(ad.location, "city", None)

            # Construire l'URL
            url = getattr(ad, "url", None)
            if not url and lbc_id:
                url = f"https://www.leboncoin.fr/annonce/{lbc_id}"

            # Insérer en base
            listing = Listing(
                alert_id=alert.id,
                leboncoin_id=lbc_id,
                title=getattr(ad, "subject", None),
                price=price,
                surface=surface,
                land_surface=land_surface,
                outside_surface=outside_surface,
                rooms=rooms,
                city=city,
                url=url,
                published_at=getattr(ad, "first_publication_date", None),
                notified_at=datetime.utcnow(),
            )
            db.add(listing)
            db.flush()

            # Envoyer le SMS
            send_sms(listing)
            new_count += 1

        alert.last_checked_at = datetime.utcnow()
        db.commit()
        logger.info(f"Alerte #{alert.id} — {new_count} nouvelle(s) annonce(s)")

    except Exception as e:
        logger.error(f"Erreur inattendue alerte #{alert_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def run_all_alerts():
    """Lance la vérification de toutes les alertes actives."""
    logger.info("=== Lancement du job horaire ===")
    db = SessionLocal()
    try:
        from app.database import Alert
        alerts = db.query(Alert).filter(Alert.is_active == True).all()
        alert_ids = [a.id for a in alerts]
        logger.info(f"{len(alert_ids)} alerte(s) active(s)")
    finally:
        db.close()

    for alert_id in alert_ids:
        check_alert(alert_id)
        time.sleep(2)  # Délai anti-Datadome entre chaque alerte


def start_scheduler():
    """Démarre le scheduler APScheduler (toutes les heures)."""
    scheduler.add_job(
        run_all_alerts,
        trigger="interval",
        hours=1,
        id="check_alerts",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler démarré — job toutes les heures")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()