import logging
import urllib.parse
import httpx
from app.config import WHATSAPP_PHONE, WHATSAPP_APIKEY

logger = logging.getLogger(__name__)


def _build_message(listing) -> str:
    """Construit le message de notification WhatsApp."""
    title = (listing.title or "Annonce")[:38]
    price = f"{listing.price:,}€".replace(",", " ") if listing.price else "Prix N/A"
    surface = f"{listing.surface}m²" if listing.surface else ""
    rooms = f"T{listing.rooms}" if listing.rooms else ""
    land = f"Terrain : {listing.land_surface}m²" if listing.land_surface else ""
    outside = f"Ext. : {listing.outside_surface}m²" if listing.outside_surface else ""
    city = listing.city or ""

    url = ""
    if listing.url:
        parts = listing.url.rstrip("/").split("/")
        url = f"leboncoin.fr/annonce/{parts[-1]}" if parts else listing.url

    details = " | ".join(filter(None, [price, surface, rooms]))
    extras = " | ".join(filter(None, [land, outside]))

    lines = [f"🏠 {title}", details]
    if extras:
        lines.append(extras)
    if city:
        lines.append(f"📍 {city}")
    if url:
        lines.append(f"🔗 {url}")

    return "\n".join(lines)


def send_sms(listing) -> bool:
    """Envoie une notification WhatsApp via Callmebot."""
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        logger.error("Callmebot : WHATSAPP_PHONE ou WHATSAPP_APIKEY non configuré dans .env")
        return False

    message = _build_message(listing)
    logger.info(f"WhatsApp notification : {message!r}")

    try:
        resp = httpx.get(
            "https://api.callmebot.com/whatsapp.php",
            params={
                "phone": WHATSAPP_PHONE,
                "text": message,
                "apikey": WHATSAPP_APIKEY,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info(f"✓ WhatsApp envoyé à {WHATSAPP_PHONE}")
            return True
        else:
            logger.error(f"Callmebot erreur {resp.status_code} : {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Callmebot exception : {e}")
        return False