"""
Engine de Inteligencia Comercial y Conexión LLM (Multi-Tenant).
Orquesta la compilación del prompt del sistema, conexión con Google Gemini,
detección de estados FSM, resolución de JSON estricto y generación de checkout Stripe.
"""

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# Importación segura de Google Generative AI
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    genai = None
    HAS_GENAI = False

PROMPT_FILE_PATH = Path(__file__).parent / "system_prompt.md"


@dataclass
class TenantConfig:
    """Configuración operativa y comercial de un tenant específico."""
    business_id: str
    business_name: str
    business_industry: str
    currency: str
    support_phone: str
    tone_style: str
    deposit_percentage: int
    cancellation_policy: str
    flight_delay_policy: str
    extra_policy: str
    legal_requirements: str
    catalog_json: str
    pricing_json: str
    business_description: str = ""
    faqs: str = ""
    booking_url: str = ""
    webhook_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Presets predeterminados para demostración y producción Multi-Tenant
DEFAULT_TENANTS: Dict[str, TenantConfig] = {
    "Traslados Riviera Maya": TenantConfig(
        business_id="TRM-CUN",
        business_name="Traslados Riviera Maya",
        business_industry="Transporte Turístico Privado & Aeroportuario",
        currency="USD",
        support_phone="+52 998 800 1234",
        tone_style="Cálido, bilingüe, eficiente, altamente servicial. Tuteo respetuoso.",
        deposit_percentage=100,
        cancellation_policy="Cancelación gratuita con 100% de reembolso hasta 24 horas antes del servicio. Menos de 24 horas aplica 50% de penalización.",
        flight_delay_policy="Monitoreo de vuelo en tiempo real. Cortesía de espera de hasta 90 minutos posteriores al aterrizaje sin costo extra.",
        extra_policy="1 maleta documentada de hasta 25 kg y 1 equipaje de mano por pasajero incluidos. Silla para infante de cortesía bajo solicitud previa.",
        legal_requirements="Pasajeros deben portar identificación oficial o pasaporte vigente. No se permite fumar dentro de las unidades.",
        catalog_json=json.dumps([
            {
                "id_sku": "SEDAN-EXEC-01",
                "nombre": "Sedán Ejecutivo (Passat / Camry)",
                "categoria": "SEDAN",
                "capacidad_personas": 3,
                "capacidad_equipaje": 3,
                "amenidades": ["A/C", "Wifi", "Agua embotellada", "Cargadores"]
            },
            {
                "id_sku": "VAN-SUB-01",
                "nombre": "Van Privada (HiAce / Transporter)",
                "categoria": "VAN",
                "capacidad_personas": 8,
                "capacidad_equipaje": 8,
                "amenidades": ["A/C doble zona", "Wifi", "Agua purificada", "Seguro de viajero"]
            },
            {
                "id_sku": "SUV-VIP-01",
                "nombre": "Chevrolet Suburban VIP",
                "categoria": "SUV_VIP",
                "capacidad_personas": 5,
                "capacidad_equipaje": 5,
                "amenidades": ["Asientos de piel", "Bebidas de cortesía", "Wifi alta velocidad", "Chofer bilingüe"]
            }
        ], indent=2, ensure_ascii=False),
        pricing_json=json.dumps([
            {
                "id_precio": "PRC-CUN-ZH-01",
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
                "id_precio": "PRC-CUN-AKUMAL-01",
                "id_sku": "VAN-SUB-01",
                "origen_zona": "Aeropuerto Cancún (CUN)",
                "destino_zona": "Akumal",
                "precio_sencillo": 115.0,
                "precio_redondo": 210.0,
                "aplica_parada_extra": 25.0
            },
            {
                "id_precio": "PRC-CUN-TULUM-01",
                "id_sku": "VAN-SUB-01",
                "origen_zona": "Aeropuerto Cancún (CUN)",
                "destino_zona": "Tulum (Centro / Zona Hotelera)",
                "precio_sencillo": 135.0,
                "precio_redondo": 250.0,
                "aplica_parada_extra": 25.0
            },
            {
                "id_precio": "PRC-CUN-SUB-ZH-01",
                "id_sku": "SUV-VIP-01",
                "origen_zona": "Aeropuerto Cancún (CUN)",
                "destino_zona": "Zona Hotelera Cancún",
                "precio_sencillo": 85.0,
                "precio_redondo": 155.0,
                "aplica_parada_extra": 25.0
            },
            {
                "id_precio": "PRC-CUN-SUB-TULUM-01",
                "id_sku": "SUV-VIP-01",
                "origen_zona": "Aeropuerto Cancún (CUN)",
                "destino_zona": "Tulum (Centro / Zona Hotelera)",
                "precio_sencillo": 220.0,
                "precio_redondo": 410.0,
                "aplica_parada_extra": 35.0
            }
        ], indent=2, ensure_ascii=False)
    ),
    "Tours Los Cabos": TenantConfig(
        business_id="TLC-CABOS",
        business_name="Los Cabos Luxury Expeditions",
        business_industry="Tours Náuticos y Traslados Turísticos de Lujo",
        currency="USD",
        support_phone="+52 624 555 7890",
        tone_style="Exclusivo, cordial, estilo resort de lujo internacional.",
        deposit_percentage=50,
        cancellation_policy="Cancelación sin penalización con 48 horas de antelación. Dentro de las 48 horas se retiene el 50% del depósito.",
        flight_delay_policy="Monitoreo satelital de vuelos privados y comerciales en San José del Cabo (SJD) y Cabo San Lucas (CSL).",
        extra_policy="Se admite equipo de golf y tablas de surf sin costo adicional con aviso de 24h.",
        legal_requirements="Documentación requerida para zarpe en tours náuticos. Prohibido el uso de calzado oscuro a bordo.",
        catalog_json=json.dumps([
            {
                "id_sku": "SUB-CABOS-01",
                "nombre": "Suburban Premier Luxury",
                "categoria": "SUV_VIP",
                "capacidad_personas": 6,
                "capacidad_equipaje": 6,
                "amenidades": ["Bebidas frías", "Toallas refrescantes", "Wifi", "Chofer concierger"]
            },
            {
                "id_sku": "SPRINTER-CABOS-01",
                "nombre": "Mercedes-Benz Sprinter VIP",
                "categoria": "MINIBUS",
                "capacidad_personas": 16,
                "capacidad_equipaje": 14,
                "amenidades": ["Pantallas HD", "Frigobar", "Asientos de piel reclinables"]
            }
        ], indent=2, ensure_ascii=False),
        pricing_json=json.dumps([
            {
                "id_precio": "PRC-SJD-SJC-01",
                "id_sku": "SUB-CABOS-01",
                "origen_zona": "Aeropuerto Los Cabos (SJD)",
                "destino_zona": "San José del Cabo Hotel Zone",
                "precio_sencillo": 65.0,
                "precio_redondo": 120.0,
                "aplica_parada_extra": 20.0
            },
            {
                "id_precio": "PRC-SJD-CSL-01",
                "id_sku": "SUB-CABOS-01",
                "origen_zona": "Aeropuerto Los Cabos (SJD)",
                "destino_zona": "Cabo San Lucas (Marina / Pacífico)",
                "precio_sencillo": 95.0,
                "precio_redondo": 175.0,
                "aplica_parada_extra": 25.0
            },
            {
                "id_precio": "PRC-SJD-TODOS-01",
                "id_sku": "SUB-CABOS-01",
                "origen_zona": "Aeropuerto Los Cabos (SJD)",
                "destino_zona": "Todos Santos Pueblo Mágico",
                "precio_sencillo": 160.0,
                "precio_redondo": 300.0,
                "aplica_parada_extra": 35.0
            }
        ], indent=2, ensure_ascii=False)
    ),
    "CDMX VIP Transfers": TenantConfig(
        business_id="CDMX-VIP-01",
        business_name="CDMX Executive & VIP Transfers",
        business_industry="Transporte Ejecutivo Corporativo y Blindado",
        currency="MXN",
        support_phone="+52 55 8900 4321",
        tone_style="Ejecutivo, formal, altamente discreto y protocolario. Tuteo respetuoso o usted.",
        deposit_percentage=100,
        cancellation_policy="Cancelaciones sin costo con al menos 12 horas de anticipación.",
        flight_delay_policy="Recepción en sala de arribos con letrero digital. Monitoreo constante de slots AICM y AIFA.",
        extra_policy="Unidades con maletero amplio. Escolta o chofer con certificación de manejo evasivo opcional.",
        legal_requirements="Contrato de servicio corporativo digital pre-firmado.",
        catalog_json=json.dumps([
            {
                "id_sku": "SEDAN-BLIND-01",
                "nombre": "Sedán Ejecutivo Premium (Blindaje Nivel III)",
                "categoria": "SEDAN_BLINDADO",
                "capacidad_personas": 3,
                "capacidad_equipaje": 2,
                "amenidades": ["Cristales blindados", "Agua gourmet", "Wifi cifrado", "Conductor certificado"]
            },
            {
                "id_sku": "SUB-EXEC-01",
                "nombre": "Chevrolet Suburban High Country",
                "categoria": "SUV_EXEC",
                "capacidad_personas": 5,
                "capacidad_equipaje": 5,
                "amenidades": ["Asientos de piel", "Clima tri-zona", "Cargadores múltiples", "Facturación inmediata"]
            }
        ], indent=2, ensure_ascii=False),
        pricing_json=json.dumps([
            {
                "id_precio": "PRC-AICM-REF-01",
                "id_sku": "SUB-EXEC-01",
                "origen_zona": "Aeropuerto CDMX (AICM T1 / T2)",
                "destino_zona": "Paseo de la Reforma / Polanco",
                "precio_sencillo": 1400.0,
                "precio_redondo": 2600.0,
                "aplica_parada_extra": 300.0
            },
            {
                "id_precio": "PRC-AICM-SF-01",
                "id_sku": "SUB-EXEC-01",
                "origen_zona": "Aeropuerto CDMX (AICM T1 / T2)",
                "destino_zona": "Santa Fe / Interlomas",
                "precio_sencillo": 1800.0,
                "precio_redondo": 3400.0,
                "aplica_parada_extra": 400.0
            },
            {
                "id_precio": "PRC-AICM-TOL-01",
                "id_sku": "SUB-EXEC-01",
                "origen_zona": "Aeropuerto CDMX (AICM T1 / T2)",
                "destino_zona": "Toluca / Metepec Corporativo",
                "precio_sencillo": 2900.0,
                "precio_redondo": 5500.0,
                "aplica_parada_extra": 500.0
            }
        ], indent=2, ensure_ascii=False)
    ),
    "Klyven Studio": TenantConfig(
        business_id="KLYVEN-STUDIO",
        business_name="Klyven Studio",
        business_industry="Estudio Independiente de Diseño Web y Desarrollo Digital",
        currency="USD",
        support_phone="+52 55 9876 5432",
        tone_style="Sofisticado, moderno, consultivo, conciso y enfocado en alto valor estético y conversión.",
        deposit_percentage=50,
        cancellation_policy="Reembolso del 100% antes de iniciar la fase de wireframing / UI. Una vez entregada la propuesta de diseño, el depósito cubre las horas de producción.",
        flight_delay_policy="Garantía de entrega puntual en sprints de 7 a 14 días laborables según el alcance acordado.",
        extra_policy="Revisiones ilimitadas durante la fase de diseño UI/UX antes del pase a desarrollo.",
        legal_requirements="Cesión de derechos de autor y entrega de código fuente o acceso de administración al liquidar el 100%.",
        catalog_json=json.dumps([
            {
                "id_sku": "WEB-LANDING-01",
                "nombre": "Landing Page de Alta Conversión",
                "categoria": "DISEÑO_WEB",
                "capacidad_personas": 1,
                "capacidad_equipaje": 1,
                "amenidades": ["Diseño UI/UX a medida", "Copywriting persuasivo", "Responsive 100%", "Animaciones fluidas", "Optimización SEO"]
            },
            {
                "id_sku": "WEB-CORP-01",
                "nombre": "Sitio Web Corporativo Completo (Hasta 5 páginas)",
                "categoria": "DISEÑO_WEB",
                "capacidad_personas": 1,
                "capacidad_equipaje": 1,
                "amenidades": ["Inicio, Servicios, Proceso, Casos de éxito y Contacto", "CMS autogestionable", "Formularios interactivos", "Velocidad ultrarrápida"]
            },
            {
                "id_sku": "WEB-REDESIGN-01",
                "nombre": "Rediseño Web Estratégico",
                "categoria": "REDISEÑO_WEB",
                "capacidad_personas": 1,
                "capacidad_equipaje": 1,
                "amenidades": ["Auditoría UX previa", "Modernización de identidad visual", "Migración limpia de contenido", "Mejora de conversión"]
            }
        ], indent=2, ensure_ascii=False),
        pricing_json=json.dumps([
            {
                "id_precio": "PRC-KLYVEN-LANDING",
                "id_sku": "WEB-LANDING-01",
                "origen_zona": "Diseño Web",
                "destino_zona": "Landing Page",
                "precio_sencillo": 450.0,
                "precio_redondo": 450.0,
                "aplica_parada_extra": 50.0
            },
            {
                "id_precio": "PRC-KLYVEN-CORP",
                "id_sku": "WEB-CORP-01",
                "origen_zona": "Diseño Web",
                "destino_zona": "Sitio Corporativo",
                "precio_sencillo": 850.0,
                "precio_redondo": 850.0,
                "aplica_parada_extra": 100.0
            },
            {
                "id_precio": "PRC-KLYVEN-REDESIGN",
                "id_sku": "WEB-REDESIGN-01",
                "origen_zona": "Rediseño Web",
                "destino_zona": "Sitio Completo",
                "precio_sencillo": 700.0,
                "precio_redondo": 700.0,
                "aplica_parada_extra": 80.0
            }
        ], indent=2, ensure_ascii=False),
        business_description="Estudio de diseño web independiente enfocado en crear sitios web distintivos, de alto rendimiento y orientados a la conversión. Combinan estrategia, diseño visual, mensajería y desarrollo para ayudar a empresas a mejorar su presencia digital.",
        faqs="Entrega en 5 a 14 días hábiles según alcance. Revisiones ilimitadas en UI/UX. Anticipo del 50% al iniciar y saldo al liquidar."
    )
}


def resolve_tenant(tenant_id: str) -> TenantConfig:
    """Resuelve dinámicamente un tenant desde SQLite o recurre a los presets predeterminados."""
    clean_id = (tenant_id or "").strip()

    # 1. Buscar en base de datos relacional SQLite
    try:
        from database import get_tenant_by_id
        db_data = get_tenant_by_id(clean_id)
        if db_data:
            cfg = db_data.get("config", {})
            services = cfg.get("services", [])
            catalog = []
            pricing = []
            
            for idx, s in enumerate(services):
                sku = s.get("id_sku") or f"SERV-{idx+1:02d}"
                name = s.get("name") or s.get("nombre") or f"Servicio {idx+1}"
                price = float(s.get("price", 0.0) or 0.0)
                desc = s.get("description", "")
                catalog.append({
                    "id_sku": sku,
                    "nombre": name,
                    "categoria": "GENERAL",
                    "capacidad_personas": 1,
                    "capacidad_equipaje": 1,
                    "amenidades": [desc] if desc else ["Servicio profesional garantizado"]
                })
                pricing.append({
                    "id_precio": f"PRC-{sku}",
                    "id_sku": sku,
                    "origen_zona": "Servicio",
                    "destino_zona": name,
                    "precio_sencillo": price,
                    "precio_redondo": price,
                    "aplica_parada_extra": 0.0
                })

            tone = cfg.get("tone_style") or "Profesional, atento, cordial, empático y orientado a asesorar y cerrar ventas."
            desc_biz = cfg.get("business_description") or "Atención personalizada para las necesidades del cliente."
            faqs = cfg.get("faqs") or "Políticas comerciales estándar de calidad y puntualidad."

            return TenantConfig(
                business_id=db_data["tenant_id"],
                business_name=db_data["business_name"],
                business_industry=db_data.get("industry") or "Servicios Profesionales",
                currency=db_data.get("currency") or "USD",
                support_phone=db_data.get("support_phone") or "",
                tone_style=tone,
                deposit_percentage=int(cfg.get("deposit_percentage", 100)),
                cancellation_policy=cfg.get("cancellation_policy") or "Políticas estándar del negocio.",
                flight_delay_policy=f"{desc_biz}. {faqs}",
                extra_policy=cfg.get("extra_policy") or "Atención y soporte prioritario.",
                legal_requirements="Términos y condiciones comerciales estándar.",
                catalog_json=json.dumps(catalog, indent=2, ensure_ascii=False),
                pricing_json=json.dumps(pricing, indent=2, ensure_ascii=False),
                business_description=desc_biz,
                faqs=faqs,
                booking_url=cfg.get("booking_url", ""),
                webhook_url=cfg.get("webhook_url", "")
            )
    except Exception:
        pass

    # 2. Buscar en presets predeterminados por business_id
    for _, t in DEFAULT_TENANTS.items():
        if t.business_id.upper() == clean_id.upper():
            return t

    # 3. Fallback a Klyven Studio o Traslados Riviera Maya
    return DEFAULT_TENANTS.get("Klyven Studio") or DEFAULT_TENANTS.get("Traslados Riviera Maya")


class ConversationEngine:
    """Motor que orquesta las llamadas al modelo de lenguaje con inyección determinista."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.system_prompt_template = self._load_prompt_template()

        if HAS_GENAI and self.api_key:
            genai.configure(api_key=self.api_key)

    def _load_prompt_template(self) -> str:
        """Carga el archivo system_prompt.md."""
        if PROMPT_FILE_PATH.exists():
            return PROMPT_FILE_PATH.read_text(encoding="utf-8")
        raise FileNotFoundError(f"No se encontró el archivo del prompt en: {PROMPT_FILE_PATH}")

    def compile_system_prompt(self, tenant: TenantConfig, history: List[Dict[str, Any]]) -> str:
        """Inyecta las variables dinámicas del tenant y el historial formateado en el prompt."""
        formatted_history = []
        for msg in history:
            role = "Cliente" if msg["role"] == "user" else "Agente de Ventas"
            content = msg.get("content", "")
            formatted_history.append(f"{role}: {content}")

        history_str = "\n".join(formatted_history) if formatted_history else "Sin mensajes previos en esta sesión."

        replacements = {
            "{{BUSINESS_ID}}": tenant.business_id,
            "{{BUSINESS_NAME}}": tenant.business_name,
            "{{BUSINESS_INDUSTRY}}": tenant.business_industry,
            "{{CURRENT_DATETIME}}": datetime.now().isoformat(),
            "{{CURRENCY}}": tenant.currency,
            "{{SUPPORT_PHONE}}": tenant.support_phone,
            "{{TONE_STYLE}}": tenant.tone_style,
            "{{DEPOSIT_PERCENTAGE}}": str(tenant.deposit_percentage),
            "{{CONVERSATION_HISTORY}}": history_str,
            "{{CANCELLATION_POLICY}}": tenant.cancellation_policy,
            "{{FLIGHT_DELAY_POLICY}}": tenant.flight_delay_policy,
            "{{EXTRA_POLICY}}": tenant.extra_policy,
            "{{LEGAL_REQUIREMENTS}}": tenant.legal_requirements,
            "{{CATALOG_JSON}}": tenant.catalog_json,
            "{{PRICING_JSON}}": tenant.pricing_json,
            "{{BUSINESS_DESCRIPTION}}": getattr(tenant, "business_description", "") or "Atención personalizada para las necesidades del cliente.",
            "{{FAQS}}": getattr(tenant, "faqs", "") or "Políticas comerciales estándar de calidad y puntualidad.",
        }

        compiled = self.system_prompt_template
        for placeholder, val in replacements.items():
            compiled = compiled.replace(placeholder, val)

        return compiled

    def generate_response(
        self,
        user_message: str,
        tenant: TenantConfig,
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Envía el mensaje al modelo y devuelve el resultado parseado estructurado.
        Utiliza REST API directo con gemini-3.5-flash-lite para máxima velocidad (< 1.5s).
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Falta la clave API de Gemini. Por favor ingrésala en la barra lateral izquierda.",
                "parsed_json": self._build_fallback_json(
                    tenant,
                    "ESTADO_4_ESCALACION_HUMANA",
                    "Por favor proporciona una clave API válida de Google Gemini en la barra lateral para continuar con el servicio automatizado."
                ),
                "stripe_url": None
            }

        compiled_prompt = self.compile_system_prompt(tenant, conversation_history)

        # Mapear modelos ultra-rápidos verificados
        candidate_models = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"]

        import requests

        last_error = "Error desconocido"
        for current_model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={self.api_key}"
            payload = {
                "system_instruction": {
                    "parts": [{"text": compiled_prompt}]
                },
                "contents": [
                    {
                        "parts": [{"text": user_message}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "response_mime_type": "application/json"
                }
            }

            try:
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        raw_text = candidates[0]["content"]["parts"][0]["text"]
                        parsed_data = self._clean_and_parse_json(raw_text, tenant)

                        stripe_url = None
                        if parsed_data.get("control_flujo", {}).get("accion_backend") == "GENERAR_CHECKOUT_STRIPE":
                            stripe_url = self._generate_simulated_stripe_checkout(parsed_data, tenant)

                        return {
                            "success": True,
                            "raw_response": raw_text,
                            "parsed_json": parsed_data,
                            "error": None,
                            "stripe_url": stripe_url
                        }
                elif resp.status_code in [404, 503, 429]:
                    last_error = f"HTTP {resp.status_code} en {current_model}: {resp.text[:100]}"
                    continue  # Probar siguiente modelo candidato
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
            except Exception as e:
                last_error = f"Error en {current_model}: {str(e)}"
                continue

        # Si todos los modelos fallaron
        return {
            "success": False,
            "error": last_error,
            "parsed_json": self._build_fallback_json(
                tenant,
                "ESTADO_4_ESCALACION_HUMANA",
                f"Disculpa la demora, nuestros sistemas están experimentando alta demanda momentánea. Por favor comunícate a nuestra línea directa de atención: {tenant.support_phone}."
            ),
            "stripe_url": None
        }

    def _clean_and_parse_json(self, raw_text: str, tenant: TenantConfig) -> Dict[str, Any]:
        """Limpia cualquier delimitador Markdown residual y parsea el objeto JSON."""
        cleaned = raw_text.strip()

        # Quitar bloques ```json ... ``` si el modelo los emitió a pesar de la instrucción
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # Localizar el bloque entre el primer { y el último }
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)

        try:
            data = json.loads(cleaned)
            # Asegurar claves esenciales
            if "mensaje_cliente" not in data:
                data["mensaje_cliente"] = "Gracias por tu mensaje. ¿Podrías confirmar los detalles de tu viaje?"
            return data
        except json.JSONDecodeError:
            # Fallback de emergencia si el texto no es JSON válido
            return self._build_fallback_json(
                tenant,
                "ESTADO_1_RECOLECCION_DATOS",
                cleaned if cleaned else "Hola, con gusto puedo asistirte. ¿A dónde deseas viajar y cuántos pasajeros son?"
            )

    def _build_fallback_json(self, tenant: TenantConfig, estado: str, mensaje: str) -> Dict[str, Any]:
        """Crea un objeto JSON conforme al esquema de la Sección 8 en situaciones excepcionales."""
        return {
            "tenant_id": tenant.business_id,
            "metadata": {
                "idioma_cliente": "es",
                "estado_conversacion": estado,
                "intencion_primaria": "consulta_general",
                "confianza_clasificacion": 0.85
            },
            "datos_operativos": {
                "servicio_solicitado": None,
                "id_sku_seleccionado": None,
                "origen": None,
                "destino": None,
                "es_servicio_redondo": False,
                "fecha_servicio": None,
                "hora_servicio": None,
                "fecha_retorno": None,
                "hora_retorno": None,
                "pasajeros": None,
                "maletas": None,
                "numero_vuelo": None,
                "unidades_requeridas": 1,
                "notas_o_solicitudes": None
            },
            "motor_precios": {
                "moneda": tenant.currency,
                "precio_unitario": None,
                "precio_total": None,
                "monto_anticipo_requerido": None,
                "requiere_cotizacion_manual": (estado == "ESTADO_4_ESCALACION_HUMANA"),
                "desglose_calculo": None
            },
            "control_flujo": {
                "accion_backend": "AVISAR_OPERADOR_HUMANO" if estado == "ESTADO_4_ESCALACION_HUMANA" else "NINGUNA",
                "campos_pendientes": ["origen", "destino", "pasajeros"],
                "motivo_bloqueo_o_escalacion": "Procesamiento de contingencia" if estado == "ESTADO_4_ESCALACION_HUMANA" else None
            },
            "mensaje_cliente": mensaje
        }

    def _generate_simulated_stripe_checkout(self, parsed_data: Dict[str, Any], tenant: TenantConfig) -> str:
        """Genera una URL estructurada de simulación de Checkout Stripe para demostración interactiva."""
        precios = parsed_data.get("motor_precios", {})
        total = precios.get("precio_total") or precios.get("monto_anticipo_requerido") or 0.0
        currency = precios.get("moneda") or tenant.currency
        sku = parsed_data.get("datos_operativos", {}).get("id_sku_seleccionado") or "SERVICE"
        
        # Parámetros codificados en URL para el checkout simulado
        params = {
            "business": tenant.business_name,
            "tenant_id": tenant.business_id,
            "sku": sku,
            "amount": f"{total:.2f}",
            "currency": currency,
            "session_id": f"cs_test_{tenant.business_id}_{int(datetime.now().timestamp())}"
        }
        query_string = urllib.parse.urlencode(params)
        return f"https://checkout.stripe.com/pay/simulated_session?{query_string}"

