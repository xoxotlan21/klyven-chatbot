"""
Servicio de Notificaciones Inmediatas al Teléfono del Dueño (Telegram / WhatsApp / Discord / Webhook).
Alerta instantáneamente cuando un nuevo cliente potencial cotiza o paga en Klyven Studio o cualquier negocio.
"""

import os
import requests
from typing import Any, Dict, Optional


def send_owner_alert(
    event_type: str,
    business_name: str,
    details: Dict[str, Any],
    telegram_bot_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    discord_webhook_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Envía una alerta en tiempo real al teléfono del dueño del negocio.
    """
    token = telegram_bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    discord_url = discord_webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")

    # Formatear mensaje
    if event_type == "NUEVO_LEAD_COTIZADO":
        icon = "🔥"
        title = f"{icon} ¡NUEVO PROSPECTO CALIFICADO EN {business_name.upper()}!"
        msg_text = (
            f"{title}\n\n"
            f"💼 *Servicio de Interés:* {details.get('service', 'Diseño Web')}\n"
            f"💰 *Presupuesto Estimado:* ${details.get('amount', 0)} {details.get('currency', 'USD')}\n"
            f"📍 *Origen/Alcance:* {details.get('origin', 'N/A')} ➡️ {details.get('destination', 'N/A')}\n"
            f"🕒 *Fecha:* {details.get('date', 'Inmediato')}\n"
            f"📱 *Contacto:* {details.get('phone', 'En chat web')}\n\n"
            f"👉 _El bot ya le presentó la cotización oficial y le ofreció apartado._"
        )
    elif event_type == "PAGO_CONFIRMADO":
        icon = "🎉"
        title = f"{icon} ¡PAGO RECIBIDO EXITOSAMENTE EN {business_name.upper()}!"
        msg_text = (
            f"{title}\n\n"
            f"💳 *Folio Orden:* {details.get('order_id')}\n"
            f"💵 *Monto Pagado:* ${details.get('amount', 0)} {details.get('currency', 'USD')}\n"
            f"👤 *Cliente:* {details.get('customer', 'Cliente Web')}\n"
            f"📦 *Concepto:* {details.get('service')}\n\n"
            f"✅ _El dinero ya fue acreditado vía Stripe y se emitió el voucher oficial._"
        )
    else:
        msg_text = f"📢 *Notificación de {business_name}:* {str(details)}"

    results = {"telegram": False, "discord": False}

    # 1. Enviar vía Telegram Bot API si está configurado
    if token and chat_id:
        try:
            tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
            r = requests.post(tg_url, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown"}, timeout=5)
            results["telegram"] = (r.status_code == 200)
        except Exception:
            pass

    # 2. Enviar vía Discord Webhook si está configurado
    if discord_url:
        try:
            r = requests.post(discord_url, json={"content": msg_text}, timeout=5)
            results["discord"] = (r.status_code == 204)
        except Exception:
            pass

    return {
        "success": True,
        "sent_to": results,
        "message": msg_text
    }

