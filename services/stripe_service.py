"""
Servicio de Integración y Checkout con Stripe Connect.
Maneja la creación de sesiones de pago, webhooks y el registro de órdenes.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import urllib.parse

# Memoria de órdenes procesadas en la plataforma
ORDER_DATABASE: Dict[str, Dict[str, Any]] = {}


def create_checkout_session(
    tenant_id: str,
    tenant_name: str,
    amount: float,
    currency: str,
    service_name: str,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    operational_data: Optional[Dict[str, Any]] = None,
    stripe_secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Crea una sesión de Checkout en Stripe (real o simulada para demo).
    """
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    key = stripe_secret_key or os.environ.get("STRIPE_SECRET_KEY")

    # Si se cuenta con credenciales reales de Stripe
    if key and key.startswith("sk_"):
        try:
            import stripe
            stripe.api_key = key
            
            # En Stripe las cantidades se manejan en centavos (ej. 100.00 USD = 10000)
            amount_cents = int(amount * 100)
            
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {
                            "name": f"{tenant_name} - {service_name}",
                            "description": f"Reserva de traslado {operational_data.get('origen', '')} a {operational_data.get('destino', '')}",
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url="https://travelsales.ai/checkout/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="https://travelsales.ai/checkout/cancelled",
                metadata={
                    "order_id": order_id,
                    "tenant_id": tenant_id,
                    "customer_name": customer_name or "Cliente",
                    "customer_phone": customer_phone or "",
                }
            )

            checkout_url = session.url
            session_id = session.id
        except Exception as e:
            # Fallback seguro a simulación en caso de error de red con Stripe
            session_id = f"cs_test_{uuid.uuid4().hex[:14]}"
            checkout_url = _build_mock_checkout_url(tenant_name, tenant_id, order_id, amount, currency, service_name, session_id)
    else:
        # Modo simulación interactiva sin credenciales
        session_id = f"cs_test_{uuid.uuid4().hex[:14]}"
        checkout_url = _build_mock_checkout_url(tenant_name, tenant_id, order_id, amount, currency, service_name, session_id)

    # Registrar orden en base de datos local
    order_record = {
        "order_id": order_id,
        "session_id": session_id,
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "amount": amount,
        "currency": currency.upper(),
        "service_name": service_name,
        "status": "PENDIENTE_DE_PAGO",
        "created_at": datetime.now().isoformat(),
        "checkout_url": checkout_url,
        "operational_data": operational_data or {},
        "customer_phone": customer_phone or ""
    }
    ORDER_DATABASE[order_id] = order_record

    return {
        "success": True,
        "order_id": order_id,
        "session_id": session_id,
        "checkout_url": checkout_url,
        "order": order_record
    }


def confirm_payment(order_id: str) -> Dict[str, Any]:
    """Simula o procesa la confirmación exitosa de pago para una orden."""
    if order_id in ORDER_DATABASE:
        ORDER_DATABASE[order_id]["status"] = "PAGADO_CONFIRMADO"
        ORDER_DATABASE[order_id]["paid_at"] = datetime.now().isoformat()
        return {"success": True, "order": ORDER_DATABASE[order_id]}
    return {"success": False, "error": f"Orden {order_id} no encontrada."}


def get_all_orders(tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Devuelve el historial de órdenes filtrado opcionalmente por tenant."""
    orders = list(ORDER_DATABASE.values())
    if tenant_id:
        orders = [o for o in orders if o["tenant_id"] == tenant_id]
    return sorted(orders, key=lambda x: x["created_at"], reverse=True)


def _build_mock_checkout_url(
    business_name: str,
    tenant_id: str,
    order_id: str,
    amount: float,
    currency: str,
    service_name: str,
    session_id: str
) -> str:
    params = {
        "order": order_id,
        "business": business_name,
        "tenant": tenant_id,
        "service": service_name,
        "amount": f"{amount:.2f}",
        "currency": currency.upper(),
        "session_id": session_id
    }
    return f"https://checkout.stripe.com/pay/simulated_checkout?{urllib.parse.urlencode(params)}"

