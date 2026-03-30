import logging
import httpx
from app.config import WHATSAPP_PHONE, WHATSAPP_APIKEY

logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1024


def _build_listing_block(listing) -> str:
    title = (listing.title or "Annonce")[:38]
    price = f"{listing.price:,}€".replace(",", " ") if listing.price else "Prix N/A"
    surface = f"{listing.surface}m²" if listing.surface else ""
    rooms = f"T{listing.rooms}" if listing.rooms else ""
    land = f"Terrain : {listing.land_surface}m²" if listing.land_surface else ""
    outside = f"Ext. : {listing.outside_surface}m²" if listing.outside_surface else ""
    city = listing.city or ""

    url = listing.url or ""

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


def _split_into_chunks(blocks: list[str], alert_name: str, total: int) -> list[str]:
    chunks = []
    current_blocks = []
    current_len = 0

    for block in blocks:
        if current_blocks and current_len + len(block) + 2 > MAX_MESSAGE_CHARS:
            chunks.append(current_blocks)
            current_blocks = [block]
            current_len = len(block)
        else:
            current_blocks.append(block)
            current_len += len(block) + 2

    if current_blocks:
        chunks.append(current_blocks)

    num_chunks = len(chunks)
    messages = []
    for i, chunk_blocks in enumerate(chunks):
        if num_chunks > 1:
            header = f"📋 {alert_name} — {total} annonce(s) [{i+1}/{num_chunks}]"
        else:
            header = f"📋 {alert_name} — {total} nouvelle(s) annonce(s)"
        messages.append(header + "\n\n" + "\n\n".join(chunk_blocks))

    return messages


def _send_single(message: str) -> bool:
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
            if "Message not sent" in resp.text:
                logger.error(f"Callmebot silent failure : {resp.text}")
                return False
            return True
        else:
            logger.error(f"Callmebot erreur {resp.status_code} : {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Callmebot exception : {e}")
        return False


def send_sms_batch(listings: list, alert_name: str) -> bool:
    if not listings:
        return True
    if not WHATSAPP_PHONE or not WHATSAPP_APIKEY:
        logger.error("Callmebot : WHATSAPP_PHONE ou WHATSAPP_APIKEY non configuré dans .env")
        return False

    blocks = [_build_listing_block(l) for l in listings]
    messages = _split_into_chunks(blocks, alert_name, len(listings))

    logger.info(f"WhatsApp batch : {len(listings)} annonce(s) → {len(messages)} message(s)")

    all_ok = True
    for i, message in enumerate(messages):
        ok = _send_single(message)
        if ok:
            logger.info(f"✓ WhatsApp [{i+1}/{len(messages)}] envoyé à {WHATSAPP_PHONE}")
        else:
            all_ok = False

    return all_ok