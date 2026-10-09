"""
Prompt Manager & Test Harness para el Agente Comercial Multi-Tenant.
Permite renderizar el prompt del sistema inyectando variables dinámicas y validar respuestas JSON.
"""

import json
from datetime import datetime
from pathlib import Path

PROMPT_FILE = Path(__file__).parent / "system_prompt.md"

# Contexto de prueba para simulación
MOCK_TENANT_DATA = {
    "BUSINESS_ID": "TC-CARIBE-01",
    "BUSINESS_NAME": "Traslados Ejecutivos del Caribe",
    "BUSINESS_INDUSTRY": "Transporte Turístico y Ejecutivo Privado",
    "CURRENT_DATETIME": datetime.now().isoformat(),
    "CURRENCY": "USD",
    "SUPPORT_PHONE": "+52 998 555 1234",
    "TONE_STYLE": "Cálido, profesional, ágil y servicial. Tuteo respetuoso.",
    "DEPOSIT_PERCENTAGE": "100",
    "CANCELLATION_POLICY": "Cancelación gratuita hasta 24 horas antes del servicio con 100% de reembolso. Menos de 24 horas aplica 50% de penalización.",
    "FLIGHT_DELAY_POLICY": "Monitoreo de vuelo en tiempo real sin costo extra. Garantía de espera de hasta 90 minutos posteriores al aterrizaje.",
    "EXTRA_POLICY": "Hasta 1 maleta de 25 kg y 1 equipaje de mano por pasajero incluidos. Silla de bebé de cortesía sujeta a solicitud previa.",
    "LEGAL_REQUIREMENTS": "Todos los pasajeros deben portar identificación oficial. Menores de edad acompañados por un adulto.",
    "CATALOG_JSON": json.dumps([
        {
            "id_sku": "SEDAN-EXEC-01",
            "nombre": "Sedán Ejecutivo Premium (Passat / Camry)",
            "categoria": "SEDAN",
            "capacidad_personas": 3,
            "capacidad_equipaje": 3,
            "amenidades": ["A/C", "Wifi", "Agua purificada", "Cargador USB"]
        },
        {
            "id_sku": "VAN-SUB-01",
            "nombre": "Van Privada Transporter / HiAce",
            "categoria": "VAN",
            "capacidad_personas": 8,
            "capacidad_equipaje": 8,
            "amenidades": ["A/C de doble zona", "Wifi", "Agua embotellada", "Seguro de viajero"]
        },
        {
            "id_sku": "SUV-SUBURBAN-01",
            "nombre": "Chevrolet Suburban VIP",
            "categoria": "SUV_VIP",
            "capacidad_personas": 5,
            "capacidad_equipaje": 5,
            "amenidades": ["A/C", "Asientos de piel", "Bebidas de cortesía", "Wifi alta velocidad"]
        }
    ], indent=2, ensure_ascii=False),
    "PRICING_JSON": json.dumps([
        {
            "id_precio": "PRC-CUN-CUN-01",
            "id_sku": "VAN-SUB-01",
            "origen_zona": "Aeropuerto Cancún (CUN)",
            "destino_zona": "Zona Hotelera Cancún",
            "precio_sencillo": 45.0,
            "precio_redondo": 80.0,
            "aplica_parada_extra": 15.0
        },
        {
            "id_precio": "PRC-CUN-PDC-01",
            "id_sku": "VAN-SUB-01",
            "origen_zona": "Aeropuerto Cancún (CUN)",
            "destino_zona": "Playa del Carmen",
            "precio_sencillo": 75.0,
            "precio_redondo": 140.0,
            "aplica_parada_extra": 20.0
        },
        {
            "id_precio": "PRC-CUN-TULUM-01",
            "id_sku": "VAN-SUB-01",
            "origen_zona": "Aeropuerto Cancún (CUN)",
            "destino_zona": "Tulum Centro / Zona Hotelera",
            "precio_sencillo": 135.0,
            "precio_redondo": 250.0,
            "aplica_parada_extra": 25.0
        }
    ], indent=2, ensure_ascii=False)
}


def render_system_prompt(tenant_data: dict, conversation_history: str = "") -> str:
    """Carga y sustituye todos los marcadores {{VARIABLE}} en el prompt de sistema."""
    template = PROMPT_FILE.read_text(encoding="utf-8")
    data = {**MOCK_TENANT_DATA, **tenant_data}
    data["CONVERSATION_HISTORY"] = conversation_history or "Sin mensajes previos en esta sesión."

    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"
        template = template.replace(placeholder, str(value))
    
    return template


if __name__ == "__main__":
    rendered = render_system_prompt(MOCK_TENANT_DATA)
    output_path = Path(__file__).parent / "prompt_renderizado_ejemplo.txt"
    output_path.write_text(rendered, encoding="utf-8")
    print(f"[OK] Prompt renderizado exitosamente en: {output_path.name}")
    print(f"Longitud total: {len(rendered)} caracteres.")

