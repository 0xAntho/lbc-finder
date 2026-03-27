import logging
import re
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal, Listing
from app.sms import send_sms_batch

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _get_ad_attribute(ad, *keys):
    attrs = getattr(ad, "attributes", []) or []
    for attr in attrs:
        if hasattr(attr, "key") and attr.key in keys:
            try:
                return int(attr.value)
            except (ValueError, TypeError):
                return attr.value
    return None


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))
    except (ValueError, TypeError):
        return None


def _extract_lbc_id(ad) -> str | None:
    for attr_name in ("list_id", "id", "ad_id"):
        val = getattr(ad, attr_name, None)
        if val:
            return str(val)

    url = getattr(ad, "url", None)
    if url:
        match = re.search(r"/(\d{6,})", url)
        if match:
            return match.group(1)

    return None


def check_alert(alert_id: int):
    db = SessionLocal()
    try:
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

        new_listings = []

        for ad in result.ads:
            lbc_id = _extract_lbc_id(ad)
            if not lbc_id:
                logger.warning(f"Annonce sans ID identifiable, ignorée : {getattr(ad, 'url', '?')}")
                continue

            existing = db.query(Listing).filter(Listing.leboncoin_id == lbc_id).first()
            if existing:
                continue

            land_surface = _get_ad_attribute(ad, "land_surface", "square_land")
            outside_surface = _get_ad_attribute(ad, "outside_surface", "square_outside")
            surface = _get_ad_attribute(ad, "square") or getattr(ad, "surface", None)
            rooms = _get_ad_attribute(ad, "rooms") or getattr(ad, "rooms", None)

            if alert.min_land_surface and land_surface:
                if land_surface < alert.min_land_surface:
                    continue

            if alert.min_outside_surface and outside_surface:
                if outside_surface < alert.min_outside_surface:
                    continue

            price = None
            if hasattr(ad, "price") and ad.price:
                try:
                    price = int(ad.price[0]) if isinstance(ad.price, list) else int(ad.price)
                except (ValueError, TypeError, IndexError):
                    pass

            city = None
            if hasattr(ad, "location") and ad.location:
                city = getattr(ad.location, "city_label", None) or getattr(ad.location, "city", None)

            url = getattr(ad, "url", None)
            if not url and lbc_id:
                url = f"https://www.leboncoin.fr/annonce/{lbc_id}"

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
                published_at=_parse_datetime(getattr(ad, "first_publication_date", None)),
                notified_at=datetime.utcnow(),
            )
            db.add(listing)
            new_listings.append(listing)

        db.flush()

        if new_listings:
            send_sms_batch(new_listings, alert.name)

        alert.last_checked_at = datetime.utcnow()
        db.commit()
        logger.info(f"Alerte #{alert.id} — {len(new_listings)} nouvelle(s) annonce(s)")

    except Exception as e:
        logger.error(f"Erreur inattendue alerte #{alert_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def run_all_alerts():
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
        time.sleep(2)


def start_scheduler():
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