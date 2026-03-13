import logging
import httpx
from app.config import (
    SMS_PROVIDER,
    OVH_APP_KEY, OVH_APP_SECRET, OVH_CONSUMER_KEY,
    OVH_SMS_SERVICE, OVH_SENDER, OVH_RECIPIENT,
    FREE_USER, FREE_PASS, PHONE_NUMBER
)

logger = logging.getLogger(__name__)

MAX_SMS_LENGTH = 160


def _build_message(listing) -> str:
    """Construit le message SMS (max 160 caractères)."""
    title = (listing.title or "Annonce")[:38]
    price = f"{listing.price:,}€".replace(",", " ") if listing.price else "Prix N/A"
    surface = f"{listing.surface}m²" if listing.surface else ""
    rooms = f"T{listing.rooms}" if listing.rooms else ""
    land = f"Terrain:{listing.land_surface}m²" if listing.land_surface else ""
    outside = f"Ext:{listing.outside_surface}m²" if listing.outside_surface else ""
    city = listing.city or ""

    # URL courte : on garde juste le domaine + ID
    url = ""
    if listing.url:
        # ex: https://www.leboncoin.fr/annonce/12345678
        parts = listing.url.rstrip("/").split("/")
        url = f"lbc.fr/{parts[-1]}" if parts else listing.url[:30]

    details = " | ".join(filter(None, [price, surface, rooms]))
    extras = " | ".join(filter(None, [land, outside]))

    lines = [title, details]
    if extras:
        lines.append(extras)
    if city:
        lines.append(city)
    if url:
        lines.append(url)

    msg = "\n".join(lines)
    return msg[:MAX_SMS_LENGTH]


def send_sms(listing) -> bool:
    """Point d'entrée principal. Retourne True si envoyé avec succès."""
    message = _build_message(listing)
    logger.info(f"SMS [{len(message)} chars]: {message!r}")

    if SMS_PROVIDER == "free":
        return _send_free(message)
    else:
        return _send_ovh(message)


def _send_free(message: str) -> bool:
    """Envoi via Free Mobile API."""
    if not FREE_USER or not FREE_PASS:
        logger.error("Free Mobile : FREE_USER ou FREE_PASS non configuré")
        return False
    try:
        resp = httpx.get(
            "https://smsapi.free-mobile.fr/sendmsg",
            params={"user": FREE_USER, "pass": FREE_PASS, "msg": message},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("SMS Free Mobile envoyé avec succès")
            return True
        else:
            logger.error(f"Free Mobile erreur {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Free Mobile exception: {e}")
        return False


def _send_ovh(message: str) -> bool:
    """Envoi via OVH SMS API."""
    if not all([OVH_APP_KEY, OVH_APP_SECRET, OVH_CONSUMER_KEY, OVH_SMS_SERVICE]):
        logger.error("OVH SMS : variables d'environnement manquantes")
        return False

    recipient = OVH_RECIPIENT or f"+{PHONE_NUMBER}"

    try:
        import ovh
        client = ovh.Client(
            endpoint="ovh-eu",
            application_key=OVH_APP_KEY,
            application_secret=OVH_APP_SECRET,
            consumer_key=OVH_CONSUMER_KEY,
        )
        client.post(
            f"/sms/{OVH_SMS_SERVICE}/jobs",
            receivers=[recipient],
            message=message,
            sender=OVH_SENDER,
            noStopClause=True,
            priority="high",
        )
        logger.info(f"SMS OVH envoyé à {recipient}")
        return True
    except Exception as e:
        logger.error(f"OVH SMS exception: {e}")
        return False