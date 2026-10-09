"""
Servicio de Despacho Operativo, Asignación de Choferes y Emisión de Vouchers.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# Flota de conductores registrados para despacho
MOCK_DRIVERS = [
    {
        "id": "DRV-01",
        "name": "Carlos Mendoza",
        "phone": "+52 998 123 4567",
        "vehicle": "Van Toyota HiAce (Placas QR-884-A)",
        "rating": 4.95,
        "status": "DISPONIBLE"
    },
    {
        "id": "DRV-02",
        "name": "Alejandro Ruiz",
        "phone": "+52 998 234 5678",
        "vehicle": "Chevrolet Suburban High Country (Placas QR-102-B)",
        "rating": 4.98,
        "status": "DISPONIBLE"
    },
    {
        "id": "DRV-03",
        "name": "Roberto Gómez",
        "phone": "+52 998 345 6789",
        "vehicle": "Volkswagen Passat Ejecutivo (Placas QR-552-C)",
        "rating": 4.90,
        "status": "EN_SERVICIO"
    }
]

DISPATCH_LOGS: List[Dict[str, Any]] = []


def assign_driver(order_id: str, operational_data: Dict[str, Any], tenant_name: str) -> Dict[str, Any]:
    """Asigna al chofer más idóneo y genera el mensaje de despacho logístico."""
    available = [d for d in MOCK_DRIVERS if d["status"] == "DISPONIBLE"]
    driver = available[0] if available else MOCK_DRIVERS[0]

    pax = operational_data.get("pasajeros") or 1
    origen = operational_data.get("origen") or "Punto de encuentro"
    destino = operational_data.get("destino") or "Destino final"
    fecha = operational_data.get("fecha_servicio") or datetime.now().strftime("%Y-%m-%d")
    hora = operational_data.get("hora_servicio") or "Por confirmar"
    vuelo = operational_data.get("numero_vuelo") or "Sin número"

    dispatch_message = (
        f"🚨 *NUEVO SERVICIO ASIGNADO - {tenant_name.upper()}*\n"
        f"📋 *Orden:* {order_id}\n"
        f"👤 *Chofer:* {driver['name']} ({driver['vehicle']})\n"
        f"📍 *Origen:* {origen}\n"
        f"🏁 *Destino:* {destino}\n"
        f"📅 *Fecha:* {fecha} a las {hora} hrs\n"
        f"👥 *Pasajeros:* {pax} | ✈️ *Vuelo:* {vuelo}\n"
        f"📱 *Instrucción:* Portar letrero digital de bienvenida en sala de arribos."
    )

    record = {
        "dispatch_id": f"DSP-{uuid.uuid4().hex[:6].upper()}",
        "order_id": order_id,
        "driver": driver,
        "created_at": datetime.now().isoformat(),
        "message": dispatch_message,
        "status": "NOTIFICADO_AL_CHOFER"
    }
    DISPATCH_LOGS.append(record)

    return {
        "success": True,
        "driver": driver,
        "dispatch_message": dispatch_message,
        "record": record
    }


def generate_voucher_data(order: Dict[str, Any], driver_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Genera los datos estructurados del voucher de confirmación con código de reserva."""
    order_id = order.get("order_id", "ORD-DEMO")
    op = order.get("operational_data", {})
    
    return {
        "voucher_id": f"VCH-{order_id}",
        "booking_code": f"CONF-{uuid.uuid4().hex[:6].upper()}",
        "tenant_name": order.get("tenant_name", "Servicio Privado"),
        "service_name": order.get("service_name", "Traslado Privado"),
        "origin": op.get("origen", "Aeropuerto"),
        "destination": op.get("destino", "Hotel"),
        "date": op.get("fecha_servicio", datetime.now().strftime("%Y-%m-%d")),
        "time": op.get("hora_servicio", "Por confirmar"),
        "passengers": op.get("pasajeros", 1),
        "flight_number": op.get("numero_vuelo", "N/A"),
        "amount_paid": order.get("amount", 0.0),
        "currency": order.get("currency", "USD"),
        "status": order.get("status", "PAGADO_CONFIRMADO"),
        "driver_name": driver_info.get("name") if driver_info else "Carlos Mendoza",
        "driver_phone": driver_info.get("phone") if driver_info else "+52 998 123 4567",
        "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=TRAVELSALES_{order_id}"
    }


def get_all_dispatches() -> List[Dict[str, Any]]:
    return list(reversed(DISPATCH_LOGS))

