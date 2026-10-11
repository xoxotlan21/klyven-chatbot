"""
Servidor Webhook API (FastAPI) para WhatsApp Cloud API, Stripe y Widget Embebible.
Expone endpoints para que cualquier sitio web externo integre el chatbot con 1 línea de código.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse
import requests
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from engine import ConversationEngine, DEFAULT_TENANTS, resolve_tenant
from services.stripe_service import confirm_payment, create_checkout_session
from services.dispatch_service import assign_driver

load_dotenv()

app = FastAPI(
    title="TravelSales.ai Gateway & Webhook Server",
    description="Servidor de integración para WhatsApp Cloud API, Stripe, API REST y Widget Embebible",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

assets_dir = Path(__file__).parent / "assets"
assets_dir.mkdir(exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "travelsales_secret_verify_token")
engine = ConversationEngine()


from database import (
    save_conversation_message,
    get_conversation_history,
    create_db_order,
    mark_order_paid,
    get_tenant_orders,
    save_or_update_tenant,
    get_tenant_by_id,
    list_all_tenants,
    save_lead,
    get_tenant_leads,
    delete_lead,
    clear_tenant_leads,
    save_unresolved_question,
    get_unresolved_questions,
    resolve_unresolved_question,
    delete_unresolved_question,
    clear_tenant_unresolved_questions,
    create_booking,
    get_tenant_bookings,
    update_booking_status,
    delete_booking,
    clear_tenant_bookings,
    get_tenant_stats,
    create_user,
    authenticate_user,
    get_user_by_token,
    logout_user,
    get_tenant_by_whatsapp,
    get_subscription_status,
    update_subscription_status,
    login_or_create_google_user
)

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    business_name: str
    industry: Optional[str] = "Servicios"

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleLoginRequest(BaseModel):
    credential: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None

class ChatRequest(BaseModel):
    tenant_id: str
    message: str
    session_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None
    preview_config: Optional[Dict[str, Any]] = None


class CreateTenantRequest(BaseModel):
    tenant_id: str
    business_name: str
    industry: str
    website_url: Optional[str] = ""
    currency: Optional[str] = "USD"
    support_phone: Optional[str] = ""
    bot_name: Optional[str] = "Asistente IA"
    bot_avatar: Optional[str] = "K"
    brand_color: Optional[str] = "#2563eb"
    theme_mode: Optional[str] = "dark"           # "dark", "light", "glass"
    header_style: Optional[str] = "brand"         # "brand", "light", "dark"
    bubble_style: Optional[str] = "circle"        # "circle", "pill"
    bubble_text: Optional[str] = "¿Podemos ayudarte?"
    position: Optional[str] = "bottom-right"      # "bottom-right", "bottom-left"
    border_radius: Optional[int] = 16
    teaser_enabled: Optional[bool] = False
    teaser_text: Optional[str] = "¿Tienes alguna duda? Escríbenos aquí"
    teaser_delay: Optional[int] = 4
    welcome_message: Optional[str] = "¡Hola! ¿En qué te podemos asesorar hoy?"
    input_placeholder: Optional[str] = "Escribe tu consulta o pedido..."
    business_description: Optional[str] = ""
    services: Optional[List[Dict[str, Any]]] = None
    faqs: Optional[str] = ""
    auto_adapt: Optional[bool] = False
    booking_url: Optional[str] = ""
    webhook_url: Optional[str] = ""


@app.get("/", response_class=HTMLResponse)
def home():
    portal_path = Path(__file__).parent / "portal.html"
    if portal_path.exists():
        return portal_path.read_text(encoding="utf-8")
    return "<h1>Portal no encontrado</h1>"


@app.get("/api/info")
def api_info():
    return {
        "status": "online",
        "service": "Klyven Studio / AI Chatbot Gateway",
        "creator_portal": "/portal",
        "embed_script": "/widget.js",
        "demo_page": "/demo"
    }


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


# ==============================================================================
# AUTO-DETECTOR DE MARCA Y COLORES DESDE CUALQUIER SITIO WEB
# ==============================================================================
def extract_brand_colors_from_html(html: str) -> str:
    """Extrae el color de marca real y vibrante analizando variables CSS, botones y cromatismo."""
    import re
    from collections import Counter

    # 1. Buscar variables CSS conocidas de colores de marca/botones
    var_matches = re.findall(
        r'--(?:primary|brand|accent|main|theme|color-primary|btn-primary)[^:]*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})',
        html,
        re.IGNORECASE
    )
    for v in var_matches:
        if len(v) == 7:
            r, g, b = int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)
            if max(r, g, b) - min(r, g, b) >= 30:
                return v.lower()

    # 2. Meta theme-color (si es colorido y no blanco/negro/gris neutro)
    theme_color = re.search(r'<meta[^>]*name=["\']theme-color["\'][^>]*content=["\'](#[0-9a-fA-F]{6})["\']', html, re.IGNORECASE)
    if theme_color:
        c = theme_color.group(1).lower()
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        if max(r, g, b) - min(r, g, b) >= 35 and max(r, g, b) < 248 and min(r, g, b) > 12:
            return c

    # 3. Buscar colores en background-color de botones, enlaces y nav
    btn_colors = re.findall(r'(?:background(?:-color)?|fill|stroke)\s*:\s*(#[0-9a-fA-F]{6})', html, re.IGNORECASE)
    btn_vibrant = []
    for h in btn_colors:
        c = h.lower()
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        if max(r, g, b) - min(r, g, b) >= 35 and max(r, g, b) < 248 and min(r, g, b) > 10:
            btn_vibrant.append(c)
    if btn_vibrant:
        return Counter(btn_vibrant).most_common(1)[0][0]

    # 4. Análisis de frecuencia de hexacromáticos
    hex_colors = re.findall(r'#([0-9a-fA-F]{6})\b', html)
    vibrant = []
    for h in hex_colors:
        c = f"#{h.lower()}"
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        chroma = max(r, g, b) - min(r, g, b)
        if chroma >= 35 and max(r, g, b) < 248 and min(r, g, b) > 10:
            vibrant.append(c)

    if vibrant:
        return Counter(vibrant).most_common(1)[0][0]

    return "#0F1B31"


@app.get("/api/extract-brand")
def api_extract_brand(url: str):
    """Inspecciona una web y extrae automáticamente su paleta de colores, logo y nombre."""
    import re
    import urllib.parse
    import requests

    target_url = url.strip()
    if not target_url.startswith("http"):
        target_url = "https://" + target_url

    parsed_domain = urllib.parse.urlparse(target_url).netloc
    clean_domain = parsed_domain.replace("www.", "")

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(target_url, headers=headers, timeout=6)
        html = resp.text

        # 1. Nombre / Título
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        raw_title = title_match.group(1).strip() if title_match else ""
        clean_title = raw_title.split("|")[0].split("-")[0].strip() or clean_domain.split(".")[0].capitalize()

        # 2. Favicon / Logo
        logo_url = f"https://www.google.com/s2/favicons?domain={clean_domain}&sz=128"
        icon_match = re.search(r'<link[^>]*rel=["\'](?:shortcut )?icon["\'][^>]*href=["\'](.*?)["\']', html, re.IGNORECASE)
        if icon_match:
            cand = icon_match.group(1)
            if cand.startswith("http"):
                logo_url = cand
            elif cand.startswith("//"):
                logo_url = "https:" + cand
            else:
                logo_url = urllib.parse.urljoin(target_url, cand)

        # 3. Color dominante con cromatismo y saturación
        dominant_color = extract_brand_colors_from_html(html)

        return {
            "status": "success",
            "url": target_url,
            "business_name": clean_title,
            "logo_url": logo_url,
            "dominant_color": dominant_color
        }
    except Exception:
        return {
            "status": "partial",
            "url": target_url,
            "business_name": clean_domain.split(".")[0].capitalize(),
            "logo_url": f"https://www.google.com/s2/favicons?domain={clean_domain}&sz=128",
            "dominant_color": "#0F1B31"
        }


class AnalyzeSiteRequest(BaseModel):
    url: str
    custom_notes: Optional[str] = ""


@app.post("/api/ai-analyze-site")
def api_ai_analyze_site(req: AnalyzeSiteRequest):
    """
    Rastrea el sitio web del cliente y usa Gemini para extraer automáticamente
    unidades, catálogo, precios reales y políticas para que el bot NO sea genérico.
    """
    import json
    import re
    import urllib.parse
    import requests

    target_url = req.url.strip()
    if target_url and not target_url.startswith("http"):
        target_url = "https://" + target_url

    site_text = ""
    if target_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            resp = requests.get(target_url, headers=headers, timeout=6)
            html = resp.text
            
            # Limpiar HTML
            cleaned = re.sub(r'<script.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<style.*?</style>', ' ', cleaned, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
            # Si el sitio es una SPA (React/Vite/Vue) con poco texto en HTML estático:
            if len(cleaned) < 400:
                js_links = re.findall(r'src=["\'](.*?\.js)["\']', html)
                spa_strings = []
                for s_link in js_links[:3]:
                    try:
                        full_js_url = urllib.parse.urljoin(target_url, s_link)
                        js_code = requests.get(full_js_url, headers=headers, timeout=5).text
                        # Extraer textos legibles
                        raw_strings = re.findall(r'["`]([a-zA-Z0-9\sÁÉÍÓÚáéíóúñÑ\$,\.\?\!\:\-\—\–]{10,180})["`]', js_code)
                        spa_strings.extend(raw_strings[:80])
                    except Exception:
                        pass
                if spa_strings:
                    cleaned += "\nTEXTO EXTRAÍDO DE LA APLICACIÓN WEB:\n" + "\n".join(spa_strings)

            site_text = cleaned[:12000]
        except Exception:
            site_text = f"URL solicitada: {target_url}"

    combined_input = f"SITIO WEB: {target_url}\nCONTENIDO EXTRAÍDO:\n{site_text}\nNOTAS DEL USUARIO:\n{req.custom_notes}"

    prompt = f"""Eres un Analista Comercial y Diseñador de Agentes IA de Élite.
Analiza el siguiente contenido extraído del sitio web real de un negocio que desea implementar un Chatbot Comercial:

--- CONTENIDO DEL SITIO ---
{combined_input}
--- FIN CONTENIDO ---

Tu objetivo es analizar profundamente de qué trata el negocio para que el Chatbot NO SEA GENÉRICO, sino hiper-especializado en este negocio real:
1. Nombre oficial del negocio y un ID sugerido en mayúsculas (ej: KLYVEN-STUDIO, DENTAL-SONRISAS, TAXI-CUN).
2. Giro o industria específica.
3. Propuesta de valor y descripción no genérica (qué hacen y qué resuelven con exactitud).
4. Moneda en la que cobran (USD, MXN, EUR, etc.).
5. Catálogo de servicios / productos / unidades reales:
   - Si es transporte/turismo: unidades (ej: Sedán Ejecutivo, Van Privada, Suburban VIP) con sus capacidades y precios si aparecen de forma explícita.
   - Si es diseño/agencia: paquetes de desarrollo, landing pages o tiendas online con precios si aparecen de forma explícita.
   - Si es salud/clínica: tratamientos o consultas con precios si aparecen de forma explícita.
   - REGLA ESTRICTA DE PRECIOS: Si en el sitio web NO se mencionan precios explícitos o tarifas numéricas para los servicios, NUNCA INVENTES UN PRECIO. En ese caso coloca null en el campo "price". Está TOTALMENTE PROHIBIDO inventar precios de mercado, suponer costos o colocar tarifas estimadas que no provengan del texto extraído.
6. Políticas, horarios de atención, garantías y ubicación mencionadas.
7. Nombre sugerido para el Asistente y un Mensaje de Bienvenida cordial y orientado a vender.
8. Color de marca dominante / característico en hexadecimal (#HEX), como el color de los botones principales o logo.
9. Texto breve para el botón flotante (máximo 4 palabras, ej: '¿Podemos ayudarte?', 'Conoce nuestros planes', 'Chatea con nosotros').

Responde ÚNICAMENTE en JSON válido con este esquema exacto:
{{
  "business_name": "Nombre Real",
  "tenant_id": "ID-SUGERIDO",
  "industry": "Giro Específico",
  "currency": "USD" o "MXN",
  "business_description": "Descripción precisa y única de este negocio...",
  "brand_color": "#HEX_COLOR",
  "bot_name": "Nombre del Asistente",
  "welcome_message": "¡Hola! Bienvenido a... ¿en qué te podemos apoyar hoy?",
  "bubble_text": "¿Podemos ayudarte?",
  "services": [
    {{
      "name": "Nombre del Servicio o Unidad",
      "price": null,
      "description": "Detalles específicos de qué incluye"
    }}
  ],
  "faqs": "Horarios, ubicación, garantías y políticas..."
}}"""

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "Falta GEMINI_API_KEY en el servidor"}

    html_detected_color = extract_brand_colors_from_html(html) if html else "#0F1B31"

    candidate_models = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_text)

                # Sanitizar servicios: asegurar que nunca haya precios inventados o nulos falsos
                if isinstance(parsed.get("services"), list):
                    for s in parsed["services"]:
                        if isinstance(s, dict):
                            p = s.get("price")
                            if p in (None, 0, "0", "null", "", "None") or str(p).strip().lower() in ("a cotizar", "consultar", "n/a", "none"):
                                s["price"] = None
                            else:
                                try:
                                    val = float(p)
                                    s["price"] = round(val, 2) if val > 0 else None
                                except (ValueError, TypeError):
                                    s["price"] = None

                # Priorizar color detectado del HTML/CSS si es vibrante, o el sugerido por IA
                final_color = html_detected_color
                if final_color in ("#0F1B31", "#2563eb", "#000000", "#ffffff") and parsed.get("brand_color") and parsed["brand_color"].startswith("#"):
                    final_color = parsed["brand_color"].strip()
                parsed["brand_color"] = final_color
                
                # Auto-persistir en la base de datos SQLite para disponibilidad inmediata
                try:
                    t_id = (parsed.get("tenant_id") or "KLYVEN-STUDIO").upper().replace(" ", "-")
                    save_or_update_tenant(
                        tenant_id=t_id,
                        business_name=parsed.get("business_name") or "Mi Negocio",
                        industry=parsed.get("industry") or "General",
                        currency=parsed.get("currency") or "USD",
                        support_phone="",
                        config_data={
                            "bot_name": parsed.get("bot_name") or "Asistente",
                            "business_description": parsed.get("business_description") or "",
                            "services": parsed.get("services") or [],
                            "faqs": parsed.get("faqs") or "",
                            "welcome_message": parsed.get("welcome_message") or "",
                            "brand_color": final_color,
                            "theme_mode": "glass",
                            "bubble_style": "pill",
                            "bubble_text": parsed.get("bubble_text") or "¿Podemos ayudarte?",
                            "position": "bottom-right"
                        }
                    )
                except Exception:
                    pass

                return {"status": "success", "data": parsed}
        except Exception:
            continue

    return {"status": "error", "message": "No se pudo procesar el análisis con IA"}


# ==============================================================================
# SEGURIDAD, AUTENTICACIÓN MULTI-TENANT & GESTIÓN DE ACCESO PRIVADO
# ==============================================================================

def get_auth_user(request: Request) -> Optional[Dict[str, Any]]:
    """Extrae y valida el usuario desde el header Authorization Bearer, cookie o query param."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
    if not token:
        token = request.cookies.get("klyven_auth_token") or request.query_params.get("token")
    if not token:
        return None
    return get_user_by_token(token)


def resolve_request_tenant(request: Request, requested_tenant_id: str) -> str:
    """Garantiza aislamiento estricto de datos: usuarios estándar solo ven su propio negocio."""
    user = get_auth_user(request)
    if user:
        if user.get("role") == "superadmin":
            return (requested_tenant_id or user.get("tenant_id") or "KLYVEN-STUDIO").strip().upper()
        return (user.get("tenant_id") or requested_tenant_id).strip().upper()
    return (requested_tenant_id or "KLYVEN-STUDIO").strip().upper()


@app.post("/api/auth/register")
def api_register_user(req: RegisterRequest):
    """Registra una nueva cuenta de negocio con contraseña cifrada y tenant aislado."""
    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Correo electrónico inválido")
    if len(req.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    if not req.business_name.strip():
        raise HTTPException(status_code=400, detail="El nombre del negocio es obligatorio")

    # Generar tenant_id único y amigable basado en el nombre de la empresa
    slug = re.sub(r"[^A-Za-z0-9]+", "-", req.business_name.strip()).strip("-").upper()
    if not slug:
        slug = f"BIZ-{uuid.uuid4().hex[:6].upper()}"
    tenant_id = slug

    # Crear tenant si no existe
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        save_or_update_tenant(
            tenant_id=tenant_id,
            business_name=req.business_name.strip(),
            industry=req.industry.strip(),
            currency="USD"
        )

    # Crear el usuario encriptado (por defecto inactivo hasta que pague su plan)
    user = create_user(
        email=email_clean,
        password=req.password,
        full_name=req.full_name.strip() or req.business_name.strip(),
        tenant_id=tenant_id,
        role="admin",
        subscription_status="inactive"
    )
    if not user:
        raise HTTPException(status_code=400, detail="Este correo electrónico ya se encuentra registrado")

    return {
        "status": "success",
        "message": "Cuenta creada con éxito",
        "token": user["token"],
        "user": user,
        "tenant_id": tenant_id,
        "subscription_status": "inactive"
    }


@app.post("/api/auth/login")
def api_login_user(req: LoginRequest):
    """Autentica a un cliente o administrador con PBKDF2 y genera token de sesión."""
    email_clean = req.email.strip().lower()
    user = authenticate_user(email_clean, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    tenant = get_tenant_by_id(user["tenant_id"]) or {}
    sub_status = user.get("subscription_status") or get_subscription_status(user["tenant_id"])
    return {
        "status": "success",
        "message": "Inicio de sesión exitoso",
        "token": user["token"],
        "user": user,
        "tenant_id": user["tenant_id"],
        "subscription_status": sub_status,
        "business_name": tenant.get("business_name", user["tenant_id"])
    }


@app.post("/api/auth/google")
def api_google_auth(req: GoogleLoginRequest):
    """Autentica o registra a un usuario instantáneamente con su cuenta de Google."""
    email = req.email
    name = req.name or ""
    picture = req.picture or ""

    if req.credential:
        try:
            import base64
            parts = req.credential.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                payload_json = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
                email = payload_json.get("email")
                name = payload_json.get("name") or (email.split("@")[0] if email else "")
                picture = payload_json.get("picture") or ""
        except Exception as e:
            print(f"[Google Auth Decode Error] {e}")

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Credenciales de Google no válidas")

    user = login_or_create_google_user(email=email, full_name=name, picture=picture)
    if not user:
        raise HTTPException(status_code=500, detail="No se pudo procesar el inicio de sesión con Google")

    tenant = get_tenant_by_id(user["tenant_id"]) or {}
    sub_status = user.get("subscription_status") or get_subscription_status(user["tenant_id"])

    return {
        "status": "success",
        "message": "Autenticación con Google exitosa",
        "token": user["token"],
        "user": user,
        "tenant_id": user["tenant_id"],
        "subscription_status": sub_status,
        "business_name": tenant.get("business_name", user["tenant_id"])
    }


def _build_oauth_redirect_uri(request: Request) -> str:
    host = request.headers.get("host", "localhost:8000")
    proto = request.headers.get("x-forwarded-proto", "")
    scheme = "https" if ("https" in proto or "trycloudflare.com" in host or "klyven" in host) else "http"
    return f"{scheme}://{host}/api/auth/google/callback"


@app.get("/api/auth/google/login")
def google_login_redirect(request: Request):
    """Redirige directamente a la pantalla oficial de Google Accounts para iniciar sesión."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = _build_oauth_redirect_uri(request)

    if not client_id:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Configuración de Google OAuth</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
            <style>
                body {{ font-family: 'Inter', sans-serif; background: #0F1B31; color: white; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
                .card {{ background: #1E293B; border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; max-width: 540px; padding: 36px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); text-align: center; }}
                h2 {{ margin: 0 0 12px 0; font-size: 1.4rem; }}
                p {{ color: #94A3B8; font-size: 0.9rem; line-height: 1.6; margin-bottom: 24px; }}
                code {{ background: #0F172A; padding: 4px 8px; border-radius: 6px; font-size: 0.82rem; color: #38BDF8; font-family: monospace; word-break: break-all; }}
                .btn {{ display: inline-flex; align-items: center; gap: 8px; background: #2563EB; color: white; padding: 12px 24px; border-radius: 10px; text-decoration: none; font-weight: 700; font-size: 0.9rem; margin-top: 10px; }}
                .btn-back {{ display: block; margin-top: 18px; color: #94A3B8; text-decoration: underline; font-size: 0.85rem; }}
                .steps {{ text-align: left; background: #0F172A; padding: 18px 20px; border-radius: 12px; margin-bottom: 20px; font-size: 0.84rem; color: #CBD5E1; }}
                .steps ol {{ margin: 0; padding-left: 20px; }}
                .steps li {{ margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div style="margin-bottom: 12px;"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" stroke-width="2"><circle cx="7.5" cy="15.5" r="5.5"></circle><path d="m21 2-9.6 9.6"></path><path d="m15.5 7.5 3 3L22 7l-3-3"></path></svg></div>
                <h2>Conectar con Google Accounts</h2>
                <p>Para abrir la pantalla oficial de Google Accounts (<b>accounts.google.com</b>), necesitas ingresar tu <b>Google Client ID</b> gratuito de Google Cloud:</p>
                <div class="steps">
                    <ol>
                        <li>Entra a <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color: #60A5FA;">Google Cloud Console</a>.</li>
                        <li>Crea un <b>ID de cliente de OAuth</b> (Tipo: <i>Aplicación web</i>).</li>
                        <li>En <b>URI de redireccionamiento autorizados</b>, ingresa:<br><code>{redirect_uri}</code></li>
                        <li>Agrega tu clave en el archivo <code>.env</code>:<br><code>GOOGLE_CLIENT_ID=tu-id.apps.googleusercontent.com</code><br><code>GOOGLE_CLIENT_SECRET=tu-secret</code></li>
                    </ol>
                </div>
                <a href="https://console.cloud.google.com/apis/credentials" target="_blank" class="btn">
                    Abrir Google Cloud Console →
                </a>
                <a href="/portal" class="btn-back">← Volver al Panel y entrar con correo/contraseña</a>
            </div>
        </body>
        </html>
        """)

    google_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"access_type=offline&"
        f"prompt=select_account"
    )
    return RedirectResponse(url=google_url)


@app.get("/api/auth/google/callback")
def google_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """Callback de Google OAuth 2.0: intercambia el código por tokens y autentica al usuario."""
    if error or not code:
        return RedirectResponse(url="/portal?google_error=cancelled")

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = _build_oauth_redirect_uri(request)


    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    try:
        t_res = requests.post(token_url, data=token_data, timeout=10)
        t_json = t_res.json()
        access_token = t_json.get("access_token")

        if not access_token:
            return RedirectResponse(url="/portal?google_error=token_failed")

        user_res = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        user_info = user_res.json()

        email = user_info.get("email")
        name = user_info.get("name") or (email.split("@")[0] if email else "Usuario")
        picture = user_info.get("picture") or ""

        if not email:
            return RedirectResponse(url="/portal?google_error=no_email")

        user = login_or_create_google_user(email=email, full_name=name, picture=picture)
        token = user["token"]
        tenant_id = user["tenant_id"]

        resp = RedirectResponse(url=f"/portal?google_token={token}&tenant={tenant_id}")
        resp.set_cookie(key="klyven_auth_token", value=token, max_age=30*86400, httponly=False, samesite="lax")
        return resp

    except Exception as e:
        print(f"[Google Callback Error] {e}")
        return RedirectResponse(url="/portal?google_error=server_error")


@app.get("/api/auth/me")
def api_get_current_user(request: Request):
    """Devuelve los datos del usuario en sesión activa con su estado de suscripción."""
    user = get_auth_user(request)
    if not user:
        return {"authenticated": False}
    tenant = get_tenant_by_id(user["tenant_id"]) or {}
    sub_status = user.get("subscription_status") or get_subscription_status(user["tenant_id"])
    return {
        "authenticated": True,
        "user": user,
        "tenant_id": user["tenant_id"],
        "subscription_status": sub_status,
        "business_name": tenant.get("business_name", user["tenant_id"])
    }


@app.post("/api/auth/logout")
def api_logout_user(request: Request):
    """Cierra la sesión y revoca el token en el servidor."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
        logout_user(token)
    return {"status": "success", "message": "Sesión cerrada correctamente"}


# ==============================================================================
# GESTIÓN DE SUSCRIPCIONES, STRIPE CHECKOUT & PAYWALL
# ==============================================================================

class ManualActivateRequest(BaseModel):
    tenant_id: str
    status: str = "active"


@app.post("/api/subscription/create-checkout-session")
def api_create_subscription_checkout(request: Request):
    """Crea una sesión de Checkout en Stripe para activar la suscripción del bot ($49 USD/mes)."""
    user = get_auth_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")

    tenant_id = user["tenant_id"]
    tenant = get_tenant_by_id(tenant_id) or {}
    business_name = tenant.get("business_name", tenant_id)

    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if stripe_key and stripe_key.startswith("sk_"):
        try:
            import stripe
            stripe.api_key = stripe_key
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Klyven Studio - Chatbot IA para {business_name}",
                            "description": "Membresía mensual: Chatbot IA 24/7 web & WhatsApp, prospectos y agenda",
                        },
                        "unit_amount": 4900,
                        "recurring": {"interval": "month"}
                    },
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=f"/portal?activated=true&tenant={tenant_id}",
                cancel_url=f"/portal?cancelled=true",
                client_reference_id=tenant_id,
                customer_email=user["email"],
                metadata={
                    "tenant_id": tenant_id,
                    "user_email": user["email"],
                    "business_name": business_name,
                    "type": "bot_subscription"
                }
            )
            return {"status": "success", "checkout_url": session.url}
        except Exception as e:
            print(f"[Stripe Checkout Error] {e}")

    # Fallback si no hay clave real de Stripe configurada aún:
    return {
        "status": "manual_checkout",
        "checkout_url": None,
        "message": "Para pagos automáticos con tarjeta configura STRIPE_SECRET_KEY. Puedes solicitar pago por WhatsApp o transferencia."
    }


@app.post("/api/subscription/activate-manual")
def api_activate_subscription_manual(request: Request, payload: ManualActivateRequest):
    """Permite al Superadministrador activar o desactivar una cuenta cliente manualmente."""
    user = get_auth_user(request)
    if not user or user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Solo el superadministrador puede activar cuentas manualmente")

    target_tenant = payload.tenant_id.strip().upper()
    update_subscription_status(target_tenant, payload.status)
    return {
        "status": "success",
        "tenant_id": target_tenant,
        "subscription_status": payload.status,
        "message": f"Estado de suscripción actualizado a {payload.status.upper()} para {target_tenant}"
    }


# ==============================================================================
# PORTAL DE CREACIÓN SAAS (Para cualquier negocio)
# ==============================================================================
@app.get("/portal", response_class=HTMLResponse)
def portal_page():
    """Portal autogestionable donde cualquier cliente crea su bot, foto, colores y catálogo."""
    portal_path = Path(__file__).parent / "portal.html"
    if portal_path.exists():
        return portal_path.read_text(encoding="utf-8")
    return "<h1>Portal no encontrado</h1>"


@app.get("/api/tenant-config")
def get_tenant_configuration(tenant_id: str):
    """Devuelve la configuración visual completa, estilo, posición y avatar del bot."""
    clean_id = (tenant_id or "").strip()
    is_klyven = "KLYVEN" in clean_id.upper()
    default_services = [
        {
            "name": "Landing Page",
            "price": 450,
            "description": "Entrega 3 días, 1 página, Ilimitadas revisiones | Alta conversión, Copy persuasivo, Responsive 100%",
            "badge": "Más pedido",
            "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=80"
        },
        {
            "name": "Business Website",
            "price": 850,
            "description": "Entrega 7 días, 5 secciones, CMS + SEO | Blog dinámico, Optimización SEO, Dominio y SSL",
            "badge": "Corporativo",
            "image_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=800&auto=format&fit=crop&q=80"
        },
        {
            "name": "Website Redesign",
            "price": 700,
            "description": "Auditoría UX, UI Premium, +Ventas | Rediseño total, Identidad digital, Carga ultra-rápida",
            "badge": "Renovación",
            "image_url": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=800&auto=format&fit=crop&q=80"
        }
    ] if is_klyven else [
        {
            "name": "Sienna XLE",
            "price": 120,
            "description": "6 pasajeros, Modelo 2018, 4 maletas | GPS, Aire acondicionado, Asientos reclinables",
            "badge": "5 fotos",
            "image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800&auto=format&fit=crop&q=80"
        },
        {
            "name": "Toyota HiAce",
            "price": 160,
            "description": "8 pasajeros, Modelo 2022, 8 maletas | Pantalla, Asientos reclinables, Aire acondicionado",
            "badge": "4 fotos",
            "image_url": "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=800&auto=format&fit=crop&q=80"
        },
        {
            "name": "Suburban VIP",
            "price": 220,
            "description": "5 pasajeros, Modelo 2023, 5 maletas | Asientos de piel, Wifi alta velocidad, Bebidas, Chofer bilingüe",
            "badge": "6 fotos",
            "image_url": "https://images.unsplash.com/photo-1563720223185-11003d516935?w=800&auto=format&fit=crop&q=80"
        }
    ]

    db_tenant = get_tenant_by_id(clean_id)
    if db_tenant:
        cfg = db_tenant.get("config", {})
        return {
            "tenant_id": db_tenant["tenant_id"],
            "business_name": db_tenant["business_name"],
            "industry": db_tenant.get("industry") or "Diseño Web y Marketing",
            "currency": db_tenant.get("currency") or "USD",
            "support_phone": db_tenant.get("support_phone") or "",
            "bot_name": cfg.get("bot_name") or "Asistente Virtual",
            "bot_avatar": cfg.get("bot_avatar") or "K",
            "brand_color": cfg.get("brand_color") or "#2563eb",
            "theme_mode": cfg.get("theme_mode") or "dark",
            "header_style": cfg.get("header_style") or "brand",
            "bubble_style": cfg.get("bubble_style") or "circle",
            "bubble_text": cfg.get("bubble_text") or "¿Podemos ayudarte?",
            "position": cfg.get("position") or "bottom-right",
            "border_radius": cfg.get("border_radius", 16),
            "teaser_enabled": cfg.get("teaser_enabled", False),
            "teaser_text": cfg.get("teaser_text") or "¿Tienes alguna duda? Escríbenos aquí",
            "teaser_delay": cfg.get("teaser_delay", 4),
            "welcome_message": cfg.get("welcome_message") or f"¡Hola! Bienvenido a {db_tenant['business_name']}. ¿En qué te podemos asesorar hoy?",
            "input_placeholder": cfg.get("input_placeholder") or "Escribe tu consulta o pedido...",
            "business_description": cfg.get("business_description") or "",
            "website_url": cfg.get("website_url") or "",
            "services": cfg.get("services") if (cfg.get("services") and len(cfg.get("services")) > 0) else default_services,
            "faqs": cfg.get("faqs") or "",
            "auto_adapt": cfg.get("auto_adapt", False),
            "booking_url": cfg.get("booking_url") or "",
            "webhook_url": cfg.get("webhook_url") or ""
        }

    # Defaults para Klyven u otros presets
    is_klyven = "KLYVEN" in clean_id.upper()
    return {
        "tenant_id": clean_id,
        "business_name": "Klyven Studio" if is_klyven else "TravelSales",
        "industry": "Diseño Web y Marketing" if is_klyven else "Turismo y Transporte",
        "bot_name": "Klyven Assistant" if is_klyven else "Asistente Oficial",
        "bot_avatar": "https://klyvenstudio.com/assets/logo-dark-C8R5adPP.png" if is_klyven else "/assets/logo-dark.png",
        "brand_color": "#0F1B31" if is_klyven else "#2563eb",
        "theme_mode": "glass",
        "header_style": "brand",
        "bubble_style": "pill",
        "bubble_text": "Hablemos de tu web" if is_klyven else "¿Podemos ayudarte?",
        "position": "bottom-right",
        "border_radius": 16,
        "teaser_enabled": True,
        "teaser_text": "¿Tienes dudas sobre tu web? Pregúntame aquí",
        "teaser_delay": 4,
        "welcome_message": "¡Hola! Bienvenido a Klyven Studio. ¿Qué tipo de sitio web o proyecto te gustaría cotizar hoy?" if is_klyven else "¡Hola! ¿En qué destino o traslado te podemos apoyar hoy?",
        "input_placeholder": "Cuéntame de tu proyecto o idea..." if is_klyven else "Escribe tu consulta o ruta...",
        "auto_adapt": False,
        "currency": "USD",
        "support_phone": "+52 55 4169 6850" if is_klyven else "",
        "booking_url": "https://calendly.com" if is_klyven else "",
        "webhook_url": "",
        "services": [
            {
                "name": "Landing Page",
                "price": 450,
                "description": "Entrega 3 días, 1 página, Ilimitadas revisiones | Alta conversión, Copy persuasivo, Responsive 100%",
                "badge": "Más pedido",
                "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=80"
            },
            {
                "name": "Business Website",
                "price": 850,
                "description": "Entrega 7 días, 5 secciones, CMS + SEO | Blog dinámico, Optimización SEO, Dominio y SSL",
                "badge": "Corporativo",
                "image_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=800&auto=format&fit=crop&q=80"
            },
            {
                "name": "Website Redesign",
                "price": 700,
                "description": "Auditoría UX, UI Premium, +Ventas | Rediseño total, Identidad digital, Carga ultra-rápida",
                "badge": "Renovación",
                "image_url": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=800&auto=format&fit=crop&q=80"
            }
        ] if is_klyven else [
            {
                "name": "Sienna XLE",
                "price": 120,
                "description": "6 pasajeros, Modelo 2018, 4 maletas | GPS, Aire acondicionado, Asientos reclinables",
                "badge": "5 fotos",
                "image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800&auto=format&fit=crop&q=80"
            },
            {
                "name": "Toyota HiAce",
                "price": 160,
                "description": "8 pasajeros, Modelo 2022, 8 maletas | Pantalla, Asientos reclinables, Aire acondicionado",
                "badge": "4 fotos",
                "image_url": "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=800&auto=format&fit=crop&q=80"
            },
            {
                "name": "Suburban VIP",
                "price": 220,
                "description": "5 pasajeros, Modelo 2023, 5 maletas | Asientos de piel, Wifi alta velocidad, Bebidas, Chofer bilingüe",
                "badge": "6 fotos",
                "image_url": "https://images.unsplash.com/photo-1563720223185-11003d516935?w=800&auto=format&fit=crop&q=80"
            }
        ]
    }


@app.post("/api/tenants")
def api_create_tenant(req: CreateTenantRequest):
    """Registra o actualiza un negocio con su catálogo real y configuración de bot."""
    config_dict = {
        "bot_name": req.bot_name,
        "bot_avatar": req.bot_avatar,
        "brand_color": req.brand_color,
        "theme_mode": req.theme_mode or "dark",
        "header_style": req.header_style or "brand",
        "bubble_style": req.bubble_style or "circle",
        "bubble_text": req.bubble_text or "¿Podemos ayudarte?",
        "position": req.position or "bottom-right",
        "border_radius": req.border_radius or 16,
        "teaser_enabled": req.teaser_enabled if req.teaser_enabled is not None else False,
        "teaser_text": req.teaser_text or "¿Tienes alguna duda? Escríbenos aquí",
        "teaser_delay": req.teaser_delay or 4,
        "welcome_message": req.welcome_message,
        "input_placeholder": req.input_placeholder,
        "website_url": req.website_url,
        "business_description": req.business_description,
        "services": req.services or [],
        "faqs": req.faqs,
        "auto_adapt": req.auto_adapt or False,
        "booking_url": req.booking_url or "",
        "webhook_url": req.webhook_url or "",
        "tone_style": "Profesional, cordial, empático y enfocado en asesorar y cerrar ventas."
    }
    saved = save_or_update_tenant(
        tenant_id=req.tenant_id.strip().upper(),
        business_name=req.business_name.strip(),
        industry=req.industry.strip(),
        currency=req.currency or "USD",
        support_phone=req.support_phone or "",
        config_data=config_dict
    )
    return {"status": "success", "tenant": saved}


@app.get("/api/tenants")
def api_list_tenants():
    """Lista todos los negocios registrados."""
    return {"tenants": list_all_tenants()}


@app.delete("/api/tenants/{tenant_id}")
def api_delete_tenant(tenant_id: str):
    """Elimina un tenant de prueba (protege KLYVEN-STUDIO)."""
    from database import delete_tenant
    ok = delete_tenant(tenant_id)
    if ok:
        return {"status": "success", "ok": True, "message": f"Tenant {tenant_id} eliminado exitosamente"}
    return {"status": "error", "ok": False, "message": f"No se pudo eliminar el tenant {tenant_id}"}


@app.get("/api/conversations")
def get_conversations(tenant_id: str = "KLYVEN-STUDIO"):
    """Lista las conversaciones y sesiones de chat registradas para un tenant."""
    from database import get_tenant_conversations
    return {"status": "success", "conversations": get_tenant_conversations(tenant_id)}


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_msgs(conversation_id: str):
    """Obtiene el historial completo de mensajes para una conversación."""
    from database import get_conversation_history
    return {"status": "success", "messages": get_conversation_history(conversation_id, limit=50)}


# ==============================================================================
# 1. VERIFICADOR REAL DE INSTALACIÓN EN LA WEB (STATUS PING)
# ==============================================================================
class VerifyInstallRequest(BaseModel):
    url: str
    tenant_id: str

@app.post("/api/verify-installation")
def api_verify_installation(req: VerifyInstallRequest):
    """Verifica en vivo si el sitio web del cliente tiene el script del widget instalado."""
    import urllib.parse
    import requests
    import re

    raw_url = req.url.strip()
    if not raw_url:
        return {"status": "error", "installed": False, "message": "Por favor ingresa la URL de tu sitio web"}
    if not raw_url.startswith("http"):
        raw_url = "https://" + raw_url

    parsed_url = urllib.parse.urlparse(raw_url)
    domain = parsed_url.hostname or raw_url

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(raw_url, headers=headers, timeout=8)
        html = resp.text

        has_widget = "widget.js" in html
        has_tenant = req.tenant_id.upper() in html.upper() if req.tenant_id else False

        if has_widget and has_tenant:
            return {
                "status": "success",
                "installed": True,
                "domain": domain,
                "message": f"¡Verificación exitosa! El widget está activo y vinculado a tu negocio en {domain}."
            }
        elif has_widget:
            return {
                "status": "warning",
                "installed": True,
                "domain": domain,
                "message": f"Se detectó widget.js en {domain}, pero verifica que el atributo data-tenant='{req.tenant_id}' coincida exactamente."
            }
        else:
            return {
                "status": "not_found",
                "installed": False,
                "domain": domain,
                "message": f"No se encontró la etiqueta <script src='.../widget.js'> en el código HTML de {domain}. Pégala antes de </body>."
            }
    except Exception as e:
        return {
            "status": "error",
            "installed": False,
            "domain": domain,
            "message": f"No se pudo conectar con {domain} ({str(e)}). Revisa que la URL sea accesible."
        }


# ==============================================================================
# 2. CAPTURA Y EXPORTACIÓN REAL DE LEADS / PROSPECTOS
# ==============================================================================
class LeadCreateRequest(BaseModel):
    tenant_id: str
    session_id: Optional[str] = ""
    customer_name: Optional[str] = ""
    contact_info: str
    service_interest: Optional[str] = ""
    notes: Optional[str] = ""

def dispatch_lead_webhook(tenant_id: str, lead_data: Dict[str, Any]):
    """Envía un webhook HTTP POST asíncrono e inmediato al endpoint configurado por el cliente."""
    import threading
    def _send():
        try:
            db_tenant = get_tenant_by_id(tenant_id)
            if not db_tenant:
                return
            cfg = db_tenant.get("config", {})
            webhook_url = (cfg.get("webhook_url") or "").strip()
            if not webhook_url or not webhook_url.startswith("http"):
                return

            biz_name = db_tenant.get("business_name", tenant_id)
            cust_name = lead_data.get("customer_name") or "Visitante Web"
            contact = lead_data.get("contact_info") or "No especificado"
            interest = lead_data.get("service_interest") or "Consulta General"
            notes = lead_data.get("notes") or ""

            if "discord.com/api/webhooks" in webhook_url:
                discord_payload = {
                    "content": f"**Nuevo Lead capturado en tu web: {biz_name}**",
                    "embeds": [{
                        "title": f"Prospecto: {cust_name}",
                        "color": 3447003,
                        "fields": [
                            {"name": "Contacto", "value": contact, "inline": True},
                            {"name": "Interés", "value": interest, "inline": True},
                            {"name": "Mensaje / Consulta", "value": notes or "Sin detalles", "inline": False}
                        ],
                        "footer": {"text": f"Klyven Studio • ID Lead #{lead_data.get('lead_id', '')}"}
                    }]
                }
                requests.post(webhook_url, json=discord_payload, timeout=6)
            elif "hooks.slack.com" in webhook_url:
                slack_payload = {
                    "text": f"*Nuevo Lead en tu web ({biz_name})*\n• *Nombre:* {cust_name}\n• *Contacto:* {contact}\n• *Interés:* {interest}\n• *Mensaje:* {notes}"
                }
                requests.post(webhook_url, json=slack_payload, timeout=6)
            else:
                body = {
                    "event": "new_lead_captured",
                    "timestamp": datetime.now().isoformat(),
                    "tenant_id": tenant_id,
                    "business_name": biz_name,
                    "lead": lead_data
                }
                requests.post(webhook_url, json=body, headers={"Content-Type": "application/json"}, timeout=6)
        except Exception as e:
            print(f"[Lead Webhook Error] {e}")

    threading.Thread(target=_send, daemon=True).start()


@app.post("/api/leads")
def api_create_lead(req: LeadCreateRequest):
    """Guarda un lead o prospecto comercial en SQLite y dispara webhook si está configurado."""
    t_id = req.tenant_id.strip().upper()
    lead_id = save_lead(
        tenant_id=t_id,
        session_id=req.session_id or "",
        customer_name=req.customer_name or "",
        contact_info=req.contact_info.strip(),
        service_interest=req.service_interest or "",
        notes=req.notes or ""
    )
    dispatch_lead_webhook(
        tenant_id=t_id,
        lead_data={
            "lead_id": lead_id,
            "session_id": req.session_id or "",
            "customer_name": req.customer_name or "",
            "contact_info": req.contact_info.strip(),
            "service_interest": req.service_interest or "",
            "notes": req.notes or ""
        }
    )
    return {"status": "success", "lead_id": lead_id}

@app.post("/api/leads/test-webhook")
def api_test_webhook(req: Dict[str, Any]):
    """Prueba el envío de un webhook de lead en vivo."""
    webhook_url = (req.get("webhook_url") or "").strip()
    tenant_id = (req.get("tenant_id") or "KLYVEN-STUDIO").strip().upper()
    if not webhook_url or not webhook_url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL de webhook inválida. Debe comenzar con http:// o https://")

    test_lead = {
        "lead_id": 999,
        "customer_name": "Cliente de Prueba (Klyven Studio)",
        "contact_info": "+52 55 1234 5678 / prueba@klyven.com",
        "service_interest": "Diseño Web Corporativo",
        "notes": "Alerta de prueba enviada desde el Panel de Chatbots de Klyven Studio para verificar tu integración.",
        "created_at": datetime.now().isoformat()
    }
    try:
        if "discord.com/api/webhooks" in webhook_url:
            body = {
                "content": "**Prueba de Webhook Exitosa** desde el Panel de Klyven Studio",
                "embeds": [{
                    "title": "Conexión de Notificaciones en Tiempo Real Verificada",
                    "description": "Tu webhook está activo y recibirá cada prospecto que deje su contacto en el chatbot.",
                    "color": 65280
                }]
            }
            resp = requests.post(webhook_url, json=body, timeout=6)
        elif "hooks.slack.com" in webhook_url:
            body = {"text": "*Prueba de Webhook Exitosa* desde el Panel de Klyven Studio. Las alertas están activas."}
            resp = requests.post(webhook_url, json=body, timeout=6)
        else:
            payload = {
                "event": "test_ping",
                "status": "success",
                "tenant_id": tenant_id,
                "message": "Prueba de conexión exitosa desde el Panel de Klyven Studio",
                "sample_lead": test_lead
            }
            resp = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}, timeout=6)

        return {
            "status": "success",
            "http_status": resp.status_code,
            "message": f"Webhook enviado exitosamente (Código HTTP {resp.status_code})"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"No se pudo conectar con el Webhook: {str(e)}"
        }

@app.get("/api/leads")
def api_get_leads(request: Request, tenant_id: str = "KLYVEN-STUDIO"):
    """Lista todos los prospectos capturados para el tenant asegurando privacidad."""
    t_id = resolve_request_tenant(request, tenant_id)
    leads = get_tenant_leads(t_id)
    return {"status": "success", "leads": leads, "count": len(leads), "tenant_id": t_id}

@app.delete("/api/leads/{lead_id}")
def api_delete_lead(lead_id: int):
    """Elimina un prospecto por su ID."""
    ok = delete_lead(lead_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return {"status": "success", "message": "Prospecto eliminado con éxito"}

@app.post("/api/leads/clear-all")
def api_clear_leads(request: Request, tenant_id: str = "KLYVEN-STUDIO"):
    """Limpia todos los prospectos de un tenant asegurando privacidad."""
    t_id = resolve_request_tenant(request, tenant_id)
    count = clear_tenant_leads(t_id)
    return {"status": "success", "message": f"{count} prospectos eliminados", "tenant_id": t_id}

@app.get("/api/leads/export-csv")
def api_export_leads_csv(request: Request, tenant_id: str = "KLYVEN-STUDIO"):
    """Descarga un archivo CSV con formato UTF-8 listo para abrir directamente en Microsoft Excel."""
    import csv
    import io

    t_id = resolve_request_tenant(request, tenant_id)
    leads = get_tenant_leads(t_id)
    output = io.StringIO()
    # Escribir BOM UTF-8 para apertura directa en Excel
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["ID Lead", "Fecha de Registro", "Nombre Prospecto", "Contacto (Teléfono/Email)", "Servicio de Interés", "Notas"])

    for l in leads:
        writer.writerow([
            l.get("lead_id", ""),
            l.get("created_at", ""),
            l.get("customer_name", "") or "No especificado",
            l.get("contact_info", ""),
            l.get("service_interest", "") or "Consulta General",
            l.get("notes", "")
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=leads_{tenant_id}.csv"
        }
    )


class LeadSubmitRequest(BaseModel):
    tenant_id: str
    customer_name: Optional[str] = None
    name: Optional[str] = None
    contact_info: Optional[str] = None
    phone: Optional[str] = None
    service_interest: Optional[str] = "Consulta General"
    notes: Optional[str] = ""
    session_id: Optional[str] = None


@app.post("/api/leads/submit")
def api_submit_lead(payload: LeadSubmitRequest):
    """Guarda un prospecto desde el formulario interactivo en el chat y despacha el webhook."""
    t_id = (payload.tenant_id or "KLYVEN-STUDIO").upper().replace(" ", "-")
    c_name = (payload.customer_name or payload.name or "Prospecto").strip()
    c_contact = (payload.contact_info or payload.phone or "Sin contacto").strip()
    s_interest = (payload.service_interest or "Consulta General").strip()
    c_notes = (payload.notes or "").strip()

    lead_id = save_lead(
        tenant_id=t_id,
        session_id=payload.session_id or f"sess_{t_id}_{int(time.time())}",
        customer_name=c_name,
        contact_info=c_contact,
        service_interest=s_interest,
        notes=c_notes
    )
    
    lead_data = {
        "lead_id": lead_id,
        "session_id": payload.session_id or "",
        "customer_name": c_name,
        "contact_info": c_contact,
        "service_interest": s_interest,
        "notes": c_notes,
        "created_at": datetime.now().isoformat()
    }
    
    # Despachar webhook configurado del tenant
    dispatch_lead_webhook(tenant_id=t_id, lead_data=lead_data)
    
    # También registrar en CRM interno y alertar al dueño
    try:
        from services.crm_service import record_lead
        from services.notification_service import send_owner_alert
        record_lead(t_id, s_interest, 0.0, "USD", notes=f"Formulario en chat: {c_contact} ({c_name})")
        send_owner_alert("NUEVO_LEAD_FORMULARIO", t_id, {
            "name": c_name,
            "contact": c_contact,
            "service": s_interest,
            "notes": c_notes
        })
    except Exception:
        pass
        
    return {
        "status": "success",
        "lead_id": lead_id,
        "customer_name": c_name,
        "service_interest": s_interest,
        "message": f"¡Gracias {c_name}! Hemos registrado tu solicitud. Un asesor se comunicará contigo de inmediato."
    }


# ==============================================================================
# PREGUNTAS SIN RESOLVER (KNOWLEDGE GAPS & 1-CLICK AÑADIR A CONOCIMIENTO)
# ==============================================================================

class ResolveQuestionRequest(BaseModel):
    question_id: int
    tenant_id: str
    answer: str

@app.get("/api/unresolved-questions")
def api_get_unresolved_questions(request: Request, tenant_id: str = "KLYVEN-STUDIO", only_unresolved: bool = False):
    """Lista las preguntas detectadas donde el bot no tuvo respuesta certera asegurando privacidad."""
    t_id = resolve_request_tenant(request, tenant_id)
    return {
        "status": "success",
        "questions": get_unresolved_questions(t_id, only_unresolved=only_unresolved),
        "tenant_id": t_id
    }

@app.post("/api/unresolved-questions/resolve")
def api_resolve_question(request: Request, req: ResolveQuestionRequest):
    """Marca la pregunta como resuelta e inyecta la respuesta oficial en el conocimiento del bot."""
    t_id = resolve_request_tenant(request, req.tenant_id)
    success = resolve_unresolved_question(req.question_id, t_id, req.answer.strip())
    if not success:
        raise HTTPException(status_code=404, detail="No se encontró la pregunta especificada")
    return {
        "status": "success",
        "message": "Pregunta agregada exitosamente a la base de conocimiento y marcada como resuelta.",
        "tenant_id": t_id
    }

@app.delete("/api/unresolved-questions/{question_id}")
def api_delete_unresolved_question(question_id: int):
    """Elimina una pregunta de la lista de pendientes."""
    ok = delete_unresolved_question(question_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    return {"status": "success", "message": "Pregunta eliminada exitosamente"}

@app.post("/api/unresolved-questions/clear-all")
def api_clear_unresolved_questions(request: Request, tenant_id: str = "KLYVEN-STUDIO"):
    """Limpia todas las preguntas registradas de un negocio para reiniciar en limpio."""
    t_id = resolve_request_tenant(request, tenant_id)
    count = clear_tenant_unresolved_questions(t_id)
    return {"status": "success", "message": f"{count} preguntas eliminadas", "tenant_id": t_id}


# ==============================================================================
# AGENDA Y RESERVAS (ADAPTABLE POR TIPO DE NEGOCIO)
# ==============================================================================

class CreateBookingRequest(BaseModel):
    tenant_id: str
    customer_name: str
    customer_contact: str
    service_name: str
    booking_date: str
    booking_time: str
    end_time: Optional[str] = ""
    business_type: Optional[str] = "general"
    resource_assigned: Optional[str] = ""
    origin: Optional[str] = ""
    destination: Optional[str] = ""
    passengers_or_qty: Optional[int] = 1
    advance_amount: Optional[float] = 0.0
    total_amount: Optional[float] = 0.0
    currency: Optional[str] = "USD"
    notes: Optional[str] = ""

class UpdateBookingStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

@app.get("/api/bookings")
def api_get_bookings(request: Request, tenant_id: str = "KLYVEN-STUDIO", status: Optional[str] = None):
    """Obtiene las reservas registradas filtradas opcionalmente por estado asegurando privacidad."""
    t_id = resolve_request_tenant(request, tenant_id)
    return {
        "status": "success",
        "bookings": get_tenant_bookings(t_id, status=status),
        "tenant_id": t_id
    }

@app.post("/api/bookings")
def api_create_booking(request: Request, payload: CreateBookingRequest):
    """Crea una reserva en el calendario operativo."""
    data = payload.dict()
    data["tenant_id"] = resolve_request_tenant(request, payload.tenant_id)
    created = create_booking(data)
    return {
        "status": "success",
        "booking": created
    }

@app.patch("/api/bookings/{booking_id}/status")
def api_update_booking_status(booking_id: str, payload: UpdateBookingStatusRequest):
    """Actualiza el estado de una reserva (CONFIRMADA, PENDIENTE, COMPLETADA, CANCELADA)."""
    ok = update_booking_status(booking_id, payload.status, payload.notes)
    if not ok:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return {
        "status": "success",
        "message": f"Estado de reserva actualizado a {payload.status.upper()}"
    }

@app.delete("/api/bookings/{booking_id}")
def api_delete_booking(booking_id: str):
    """Elimina una reserva operativa por su identificador."""
    ok = delete_booking(booking_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return {"status": "success", "message": "Reserva eliminada con éxito"}

@app.post("/api/bookings/clear-all")
def api_clear_bookings(request: Request, tenant_id: str = "KLYVEN-STUDIO"):
    """Limpia todas las reservas registradas de un negocio para iniciar en limpio."""
    t_id = resolve_request_tenant(request, tenant_id)
    count = clear_tenant_bookings(t_id)
    return {"status": "success", "message": f"{count} reservas eliminadas", "tenant_id": t_id}


# ==============================================================================
# ESTADÍSTICAS Y MÉTRICAS DE CONVERSIÓN POR PERIODO
# ==============================================================================

@app.get("/api/stats")
def api_get_stats(request: Request, tenant_id: str = "KLYVEN-STUDIO", period: str = "30d"):
    """Calcula KPIs, tasa de conversión, top preguntas y analítica por periodo asegurando privacidad."""
    t_id = resolve_request_tenant(request, tenant_id)
    return {
        "status": "success",
        "stats": get_tenant_stats(t_id, period=period)
    }


# ==============================================================================
# 4. CARGA REAL DE DOCUMENTOS Y CATÁLOGOS (PDF / TXT)
# ==============================================================================
@app.post("/api/upload-knowledge")
async def api_upload_knowledge(
    file: UploadFile = File(...),
    tenant_id: str = Form("KLYVEN-STUDIO"),
    custom_notes: Optional[str] = Form("")
):
    """Extrae el contenido de un PDF o TXT y usa Gemini para estructurar servicios y políticas."""
    import io
    import json
    import requests
    import pypdf

    content_bytes = await file.read()
    filename = file.filename or "documento"
    extracted_text = ""

    if filename.lower().endswith(".pdf"):
        try:
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            extracted_text = "\n".join(pages_text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al procesar el archivo PDF: {str(e)}")
    else:
        try:
            extracted_text = content_bytes.decode("utf-8")
        except Exception:
            extracted_text = content_bytes.decode("latin-1", errors="ignore")

    cleaned_text = extracted_text.strip()
    if len(cleaned_text) < 20:
        raise HTTPException(status_code=400, detail="El documento no contiene texto legible suficiente.")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "Falta GEMINI_API_KEY en el servidor"}

    sample_text = cleaned_text[:14000]
    prompt = f"""Eres un Especialista en Extracción de Datos Comerciales para Chatbots IA.
Analiza el siguiente documento ({filename}) subido por el negocio {tenant_id}:

--- CONTENIDO DEL DOCUMENTO ---
{sample_text}
--- NOTAS COMPLEMENTARIAS ---
{custom_notes or ''}
--- FIN CONTENIDO ---

Extrae con exactitud:
1. Lista de servicios o productos reales mencionados. REGLA ESTRICTA DE PRECIOS: Solo coloca precio numérico en "price" si está explícitamente indicado en el documento. Si no se menciona precio explícito o es a cotizar, coloca null en "price". Está TOTALMENTE PROHIBIDO inventar precios o suponer tarifas que no estén en el documento.
2. Políticas relevantes, garantías, formas de pago y horarios.
3. Breve resumen de lo descubierto.

Responde ÚNICAMENTE en JSON válido con este formato:
{{
  "services": [
    {{
      "name": "Nombre del servicio/producto",
      "price": null,
      "description": "Detalle de lo que incluye"
    }}
  ],
  "faqs": "Políticas, garantías y condiciones clave...",
  "summary": "Resumen claro de lo extraído..."
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
    }

    try:
        resp = requests.post(url, json=payload, timeout=16)
        if resp.status_code == 200:
            raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)

            # Sanitización estricta: asegurar que nunca haya precios inventados
            if isinstance(parsed, dict) and isinstance(parsed.get("services"), list):
                for s in parsed["services"]:
                    if isinstance(s, dict):
                        p = s.get("price")
                        if p in (None, 0, "0", "null", "", "None") or str(p).strip().lower() in ("a cotizar", "consultar", "n/a", "none"):
                            s["price"] = None
                        else:
                            try:
                                val = float(p)
                                s["price"] = round(val, 2) if val > 0 else None
                            except (ValueError, TypeError):
                                s["price"] = None

            return {
                "status": "success",
                "filename": filename,
                "chars_extracted": len(cleaned_text),
                "data": parsed
            }
        else:
            return {"status": "error", "message": f"Error de API Gemini: {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==============================================================================
# WIDGET EMBEDDABLE & DEMO PAGE
# ==============================================================================
@app.get("/widget.js")
def get_widget_script():
    """Sirve el script del widget para sitios web externos."""
    widget_path = Path(__file__).parent / "widget.js"
    if widget_path.exists():
        return FileResponse(widget_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="widget.js no encontrado")


@app.get("/demo", response_class=HTMLResponse)
def demo_client_website(request: Request):
    """Página de demostración que simula el sitio web de un cliente con el widget integrado."""
    tenant = request.query_params.get("tenant", "TRM-CUN")
    demo_path = Path(__file__).parent / "demo_client_website.html"
    if demo_path.exists():
        html = demo_path.read_text(encoding="utf-8")
        html = html.replace('data-tenant="TRM-CUN"', f'data-tenant="{tenant}"')
        return html
    return "<h1>Sitio de demostración</h1>"


@app.get("/klyven", response_class=HTMLResponse)
def klyven_demo_page():
    """Página de Klyven Studio con el bot oficial de ventas integrado."""
    klyven_path = Path(__file__).parent / "klyven_demo.html"
    if klyven_path.exists():
        return klyven_path.read_text(encoding="utf-8")
    return "<h1>Klyven Studio Demo</h1>"


@app.get("/chat/{tenant_id}", response_class=HTMLResponse)
def standalone_chat_page(tenant_id: str):
    """Página de chat independiente y responsive a pantalla completa para redes sociales y QR."""
    chat_path = Path(__file__).parent / "chat.html"
    if chat_path.exists():
        html = chat_path.read_text(encoding="utf-8")
        clean_t = tenant_id.upper().replace(" ", "-")
        html = html.replace('data-tenant="KLYVEN-STUDIO"', f'data-tenant="{clean_t}"')
        return html
    return "<h1>Página de chat no encontrada</h1>"


@app.get("/api/qr/{tenant_id}")
def api_generate_qr(tenant_id: str, request: Request, download: Optional[bool] = False):
    """Genera una imagen PNG de código QR apuntando a la URL directa del chatbot para el tenant."""
    import qrcode
    import io
    
    t_id = tenant_id.upper().replace(" ", "-")
    host_header = request.headers.get("host") or "localhost:8000"
    scheme = "https" if "https" in str(request.url) or "onrender.com" in host_header else request.url.scheme
    chat_url = f"{scheme}://{host_header}/chat/{t_id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(chat_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0F1B31", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    disposition = f"attachment; filename=qr_{t_id}.png" if download else f"inline; filename=qr_{t_id}.png"
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "public, max-age=1800"
        }
    )



# ==============================================================================
# API REST UNIVERSAL DE CHAT (Para el Widget y Sitios Web)
# ==============================================================================
@app.post("/api/chat")
def api_chat(payload: ChatRequest):
    # Si el portal envía configuración en vivo de vista previa, actualizarla al instante:
    if payload.preview_config:
        try:
            pcfg = payload.preview_config
            t_id = (payload.tenant_id or "KLYVEN-STUDIO").upper().replace(" ", "-")
            support_phone = pcfg.get("support_phone") or ""
            save_or_update_tenant(
                tenant_id=t_id,
                business_name=pcfg.get("business_name") or "Mi Negocio",
                industry=pcfg.get("industry") or "General",
                currency=pcfg.get("currency") or "USD",
                support_phone=support_phone,
                config_data={
                    "bot_name": pcfg.get("bot_name") or "Asistente",
                    "business_description": pcfg.get("business_description") or "",
                    "services": pcfg.get("services") or [],
                    "faqs": pcfg.get("faqs") or "",
                    "welcome_message": pcfg.get("welcome_message") or "",
                    "brand_color": pcfg.get("brand_color") or "#0F1B31",
                    "theme_mode": pcfg.get("theme_mode") or "glass",
                    "bubble_style": pcfg.get("bubble_style") or "pill",
                    "bubble_text": pcfg.get("bubble_text") or "Hablemos de tu web",
                    "position": pcfg.get("position") or "bottom-right",
                    "booking_url": pcfg.get("booking_url") or "",
                    "webhook_url": pcfg.get("webhook_url") or ""
                }
            )
        except Exception:
            pass

    matched_tenant = resolve_tenant(payload.tenant_id)

    session_id = payload.session_id or f"sess_{payload.tenant_id}_{abs(hash(payload.message)) % 100000}"

    # 1. Guardar mensaje entrante del usuario en la base de datos
    save_conversation_message(session_id, matched_tenant.business_id, "user", payload.message)

    # 2. Cargar historial conversacional de la base de datos
    history = get_conversation_history(session_id)

    # 3. Generar respuesta determinista con la IA
    result = engine.generate_response(
        user_message=payload.message,
        tenant=matched_tenant,
        conversation_history=history
    )

    parsed = result.get("parsed_json", {})
    cliente_msg = parsed.get("mensaje_cliente", "Gracias por tu mensaje.")
    control_flujo = parsed.get("control_flujo", {})
    motor_precios = parsed.get("motor_precios", {})
    datos_operativos = parsed.get("datos_operativos", {})

    # 4. Guardar respuesta del asistente en la base de datos
    save_conversation_message(session_id, matched_tenant.business_id, "assistant", cliente_msg, payload=parsed)

    checkout_url = None
    order_id = None
    price = motor_precios.get("precio_total")
    currency = motor_precios.get("moneda") or matched_tenant.currency

    # 5. Si el cliente confirmó la compra, crear orden real en base de datos
    if control_flujo.get("accion_backend") == "GENERAR_CHECKOUT_STRIPE":
        sku = datos_operativos.get("id_sku_seleccionado") or "RESERVA"
        ord_res = create_checkout_session(
            tenant_id=matched_tenant.business_id,
            tenant_name=matched_tenant.business_name,
            amount=price or 0.0,
            currency=currency,
            service_name=sku,
            operational_data=datos_operativos
        )
        checkout_url = ord_res["checkout_url"]

        # Insertar orden persistente en SQLite
        order_id = create_db_order(
            tenant_id=matched_tenant.business_id,
            amount=price or 0.0,
            currency=currency,
            service_name=sku,
            operational_data=datos_operativos,
            stripe_session_id=ord_res["session_id"],
            conversation_id=session_id
        )

        # Registrar en CRM y alertar al dueño
        try:
            from services.crm_service import record_lead
            from services.notification_service import send_owner_alert
            record_lead(matched_tenant.business_id, sku, price or 0.0, currency, notes=f"Orden {order_id} generada en web")
            send_owner_alert("NUEVO_LEAD_COTIZADO", matched_tenant.business_name, {
                "service": sku,
                "amount": price or 0.0,
                "currency": currency,
                "origin": datos_operativos.get("origen", "N/A"),
                "destination": datos_operativos.get("destino", "N/A"),
                "date": datos_operativos.get("fecha_servicio", "Próxima")
            })
        except Exception:
            pass

    # Auto-detección y guardado de Prospecto (Lead) en SQLite
    import re
    msg_text = payload.message
    email_m = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', msg_text)
    phone_m = re.search(r'(?:\+?52\s?)?(?:\(?\d{2,3}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}', msg_text)
    name_m = re.search(r'(?:me llamo|mi nombre es|soy)\s+([A-Za-záéíóúÁÉÍÓÚñÑ]+(?:\s+[A-Za-záéíóúÁÉÍÓÚñÑ]+)?)', msg_text, re.IGNORECASE)
    extracted_name = name_m.group(1).strip().title() if name_m else None
    resolved_lead_name = datos_operativos.get("nombre_cliente") or extracted_name or "Prospecto Web"

    if email_m or phone_m:
        contact_str = email_m.group(0) if email_m else phone_m.group(0)
        try:
            lead_id = save_lead(
                tenant_id=matched_tenant.business_id,
                session_id=session_id,
                customer_name=resolved_lead_name,
                contact_info=contact_str,
                service_interest=datos_operativos.get("id_sku_seleccionado") or "",
                notes=msg_text[:200]
            )
            dispatch_lead_webhook(
                tenant_id=matched_tenant.business_id,
                lead_data={
                    "lead_id": lead_id,
                    "session_id": session_id,
                    "customer_name": resolved_lead_name,
                    "contact_info": contact_str,
                    "service_interest": datos_operativos.get("id_sku_seleccionado") or "",
                    "notes": msg_text[:200]
                }
            )
        except Exception:
            pass

    # Auto-creación de Reserva en Agenda Operativa en tiempo real (100% Funcional)
    booking_keywords = ["agendar", "cita", "reserva", "reservar", "reunion", "reunión", "apartar", "programar", "turno", "traslado", "rentar", "tour"]
    has_bk_intent = (
        control_flujo.get("accion_backend") in ["AGENDAR_RESERVA", "CREAR_RESERVA", "GENERAR_CHECKOUT_STRIPE"] or
        any(k in msg_text.lower() for k in booking_keywords) or
        bool(datos_operativos.get("fecha_servicio"))
    )

    if has_bk_intent and (email_m or phone_m or datos_operativos.get("nombre_cliente") or datos_operativos.get("fecha_servicio")):
        try:
            extracted_name = None
            name_m = re.search(r'(?:me llamo|mi nombre es|soy)\s+([A-Za-záéíóúÁÉÍÓÚñÑ]+(?:\s+[A-Za-záéíóúÁÉÍÓÚñÑ]+)?)', msg_text, re.IGNORECASE)
            if name_m:
                extracted_name = name_m.group(1).strip().title()
            cust_name = datos_operativos.get("nombre_cliente") or extracted_name or "Cliente Web"
            cust_contact = (email_m.group(0) if email_m else (phone_m.group(0) if phone_m else "")) or datos_operativos.get("contacto_cliente") or "Por confirmar"
            srv_name = datos_operativos.get("servicio_solicitado") or datos_operativos.get("id_sku_seleccionado") or "Consulta y Asesoría"
            srv_date = datos_operativos.get("fecha_servicio") or datetime.now().strftime("%Y-%m-%d")
            srv_time = datos_operativos.get("hora_servicio") or "11:00"

            created_bk = create_booking({
                "tenant_id": matched_tenant.business_id,
                "business_type": getattr(matched_tenant, 'business_industry', 'general').lower(),
                "customer_name": cust_name,
                "customer_contact": cust_contact,
                "service_name": srv_name,
                "booking_date": srv_date,
                "booking_time": srv_time,
                "end_time": "",
                "resource_assigned": "Equipo Comercial",
                "origin": datos_operativos.get("origen") or "",
                "destination": datos_operativos.get("destino") or "",
                "passengers_or_qty": datos_operativos.get("numero_pasajeros") or 1,
                "status": "PENDIENTE",
                "advance_amount": 0.0,
                "total_amount": float(price or 0.0),
                "currency": currency,
                "notes": f"Agendado en tiempo real desde el Chatbot Web (Sesión: {session_id}). Mensaje: {msg_text[:140]}"
            })

            if created_bk and created_bk.get("booking_id"):
                b_code = created_bk["booking_id"]
                if b_code not in cliente_msg:
                    cliente_msg += f"\n\n**Solicitud registrada en tu agenda:** Folio `#{b_code}`. Nuestro equipo la revisará y confirmará a la brevedad."
        except Exception:
            pass

    # Detección y registro automático de Preguntas Sin Resolver (Knowledge Gaps)
    low_resp = cliente_msg.lower()
    unresolved_indicators = [
        "no dispongo", "no cuento con", "te sugiero contactar", "no tengo esa información",
        "no tengo información", "no cuento en mi catálogo", "no estoy seguro",
        "te sugiero consultar con un asesor", "te recomiendo contactar", "no tengo detalles",
        "un asesor te brindará", "no dispongo de los detalles"
    ]
    if any(ind in low_resp for ind in unresolved_indicators) and len(payload.message.strip()) > 5:
        try:
            save_unresolved_question(
                tenant_id=matched_tenant.business_id,
                question_text=payload.message.strip(),
                bot_response=cliente_msg,
                conversation_id=session_id
            )
        except Exception:
            pass

    # Derivación a WhatsApp si el usuario lo solicita
    supp_phone = (payload.preview_config.get("support_phone") if payload.preview_config else "") or getattr(matched_tenant, "support_phone", "") or ""
    clean_phone = re.sub(r'[^0-9]', '', supp_phone)
    if clean_phone and len(clean_phone) >= 8:
        low_msg = payload.message.lower()
        if any(w in low_msg for w in ["whatsapp", "asesor", "humano", "persona", "hablar con alguien", "teléfono", "telefono", "contacto", "llamar", "celular", "whats"]):
            import urllib.parse
            biz_display = getattr(matched_tenant, "business_name", "ustedes")
            encoded_txt = urllib.parse.quote(f"Hola {biz_display}, estoy en su página web y me gustaría hablar con un asesor.")
            wa_link = f"https://wa.me/{clean_phone}?text={encoded_txt}"
            if "wa.me" not in cliente_msg:
                cliente_msg += f"\n\n[Hablar por WhatsApp]({wa_link})"

    # Agendamiento directo de citas o llamadas (Calendly / Cal.com / Google Calendar)
    book_url = (payload.preview_config.get("booking_url") if payload.preview_config else "") or getattr(matched_tenant, "booking_url", "") or ""
    if not book_url:
        try:
            db_t_match = get_tenant_by_id(matched_tenant.business_id)
            if db_t_match:
                book_url = db_t_match.get("config", {}).get("booking_url", "")
        except Exception:
            pass

    clean_book_url = (book_url or "").strip()
    if clean_book_url and clean_book_url.startswith("http"):
        low_msg = payload.message.lower()
        if any(w in low_msg for w in ["agendar", "cita", "llamada", "reunión", "reunion", "calendario", "reservar", "horario", "demo", "junta", "meet", "videollamada"]):
            if clean_book_url not in cliente_msg:
                cliente_msg += f"\n\n[Agendar Cita o Llamada]({clean_book_url})"

    # 7. Inyección de Carrusel Visual de Tarjetas si el usuario consulta el catálogo, unidades, flota, precios o fotos
    services_for_carousel = []
    if payload.preview_config and payload.preview_config.get("services"):
        services_for_carousel = payload.preview_config.get("services")
    else:
        try:
            db_t_c = get_tenant_by_id(matched_tenant.business_id)
            if db_t_c:
                services_for_carousel = db_t_c.get("config", {}).get("services", [])
        except Exception:
            pass

    if not services_for_carousel:
        is_klyv_check = "KLYVEN" in matched_tenant.business_id.upper()
        if is_klyv_check:
            services_for_carousel = [
                {"name": "Landing Page", "price": 450, "description": "Entrega 3 días, 1 página, Ilimitadas revisiones | Alta conversión, Copy persuasivo, Responsive 100%", "badge": "Más pedido", "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=80"},
                {"name": "Business Website", "price": 850, "description": "Entrega 7 días, 5 secciones, CMS + SEO | Blog dinámico, Optimización SEO, Dominio y SSL", "badge": "Corporativo", "image_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=800&auto=format&fit=crop&q=80"},
                {"name": "Website Redesign", "price": 700, "description": "Auditoría UX, UI Premium, +Ventas | Rediseño total, Identidad digital, Carga ultra-rápida", "badge": "Renovación", "image_url": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=800&auto=format&fit=crop&q=80"}
            ]
        elif "TRM" in matched_tenant.business_id.upper() or "TRANS" in matched_tenant.business_id.upper():
            services_for_carousel = [
                {"name": "Sienna XLE", "price": 120, "description": "6 pasajeros, Modelo 2018, 4 maletas | GPS, Aire acondicionado, Asientos reclinables", "badge": "5 fotos", "image_url": "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800&auto=format&fit=crop&q=80"},
                {"name": "Toyota HiAce", "price": 160, "description": "8 pasajeros, Modelo 2022, 8 maletas | Pantalla, Asientos reclinables, Aire acondicionado", "badge": "4 fotos", "image_url": "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=800&auto=format&fit=crop&q=80"},
                {"name": "Suburban VIP", "price": 220, "description": "5 pasajeros, Modelo 2023, 5 maletas | Asientos de piel, Wifi alta velocidad, Bebidas, Chofer bilingüe", "badge": "6 fotos", "image_url": "https://images.unsplash.com/photo-1563720223185-11003d516935?w=800&auto=format&fit=crop&q=80"}
            ]

    catalog_triggers = [
        "servicio", "servicios", "paquete", "paquetes", "unidad", "unidades", 
        "flota", "vehículo", "vehiculo", "vehículos", "vehiculos", "auto", "autos", 
        "carro", "carros", "camioneta", "camionetas", "modelo", "modelos", 
        "opciones", "catalogo", "catálogo", "foto", "fotos", "imagen", "imagenes", 
        "imágenes", "precio", "precios", "ofrecen", "tienen", "mostrar", "muestrame", 
        "muéstrame", "ver más", "ver mas", "cotizar"
    ]
    user_asks_catalog = any(trig in payload.message.lower() for trig in catalog_triggers)
    if user_asks_catalog and services_for_carousel and ":::carousel" not in cliente_msg:
        has_list_dump = bool(re.search(r'(?:\d+[\.\)]\s+|[-*•]\s+.*?\n|Actualmente ofrecemos|los siguientes planes|nuestros paquetes|nuestros servicios|ofrecemos las siguientes|ofrecemos los siguientes)', cliente_msg, re.IGNORECASE))
        if has_list_dump:
            greeting_match = re.search(r'(¡?Hola[^.!?\n]*[.!?])', cliente_msg, re.IGNORECASE)
            greeting = greeting_match.group(1) if greeting_match else f"¡Hola! Bienvenido a **{matched_tenant.business_name}**."
            cliente_msg = (
                f"{greeting} Con gusto te comparto nuestras opciones y soluciones disponibles. "
                f"Puedes deslizar las siguientes tarjetas para conocer los detalles, características y cotizar:"
            )
        else:
            cliente_msg = cliente_msg.strip()
            if not any(w in cliente_msg.lower() for w in ["tarjeta", "tarjetas", "desliza", "carrusel"]):
                cliente_msg += "\n\nPuedes deslizar las siguientes tarjetas para conocer los detalles y cotizar:"

        carousel_cards = []
        for s in services_for_carousel:
            s_name = s.get("name") or s.get("nombre") or "Servicio"
            s_price = s.get("price") or 0
            s_img = s.get("image_url") or s.get("image") or ""
            s_badge = s.get("badge") or ("Foto" if s_img else "")
            s_desc = s.get("description") or ""

            specs = []
            tags = []
            if "|" in s_desc:
                p_specs, p_tags = s_desc.split("|", 1)
                for part in p_specs.split(","):
                    part = part.strip()
                    if part:
                        words = part.split(" ", 1)
                        if len(words) == 2 and (words[0].isdigit() or any(c.isdigit() for c in words[0])):
                            specs.append({"label": words[1].upper()[:9], "val": words[0]})
                        elif ":" in part:
                            sp_k, sp_v = part.split(":", 1)
                            specs.append({"label": sp_k.strip().upper()[:9], "val": sp_v.strip()})
                        else:
                            specs.append({"label": "DETALLE", "val": part})
                for t in p_tags.split(","):
                    t = t.strip()
                    if t:
                        tags.append(t)
            else:
                for t in s_desc.split(","):
                    t = t.strip()
                    if t:
                        tags.append(t)

            if not specs and s_price and float(s_price) > 0:
                specs.append({"label": "PRECIO", "val": f"${float(s_price):,.0f} {currency}"})
                specs.append({"label": "ESTADO", "val": "Disponible"})
            elif not specs:
                specs.append({"label": "ESTADO", "val": "Disponible"})

            carousel_cards.append({
                "title": s_name,
                "image": s_img,
                "badge": s_badge,
                "price": f"${float(s_price):,.0f} {currency}" if (s_price and float(s_price) > 0) else "",
                "specs": specs[:3],
                "tags": tags[:4],
                "action_label": "Ver más",
                "action_query": f"Me interesa {s_name}"
            })

        if carousel_cards:
            carousel_json = json.dumps(carousel_cards, ensure_ascii=False)
            cliente_msg += f"\n\n:::carousel\n{carousel_json}\n:::"

    # 8. Inyección de Formulario Interactivo de Lead si el usuario solicita cotización o contratación
    lead_triggers = ["me interesa", "cotizar", "cotización", "cotizacion", "contratar", "adquirir", "solicitar cotización", "presupuesto", "hablar con alguien", "dejar mis datos", "quiero contratar"]
    low_u_msg = payload.message.lower()
    if any(trig in low_u_msg for trig in lead_triggers) and ":::lead_form" not in cliente_msg:
        matched_service = ""
        if "me interesa " in low_u_msg:
            matched_service = payload.message[low_u_msg.find("me interesa ") + 12:].strip()
        elif datos_operativos.get("id_sku_seleccionado"):
            matched_service = str(datos_operativos.get("id_sku_seleccionado"))
            
        form_payload = {
            "service": matched_service or "Consulta General",
            "title": f"Cotizar {matched_service}" if matched_service else "Solicitar Cotización Inmediata"
        }
        cliente_msg += f"\n\n:::lead_form\n{json.dumps(form_payload, ensure_ascii=False)}\n:::"

    return {
        "reply": cliente_msg,
        "session_id": session_id,
        "state": parsed.get("metadata", {}).get("estado_conversacion"),
        "checkout_url": checkout_url,
        "order_id": order_id,
        "price": price,
        "currency": currency,
        "payload": parsed
    }


# ==============================================================================
# WEBHOOK WHATSAPP CLOUD API (META)
# ==============================================================================
@app.get("/webhook/whatsapp")
def verify_whatsapp_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token inválido")


def send_whatsapp_cloud_reply(phone_number_id: str, to_phone: str, text: str, token: Optional[str] = None):
    """Envía la respuesta automática generada por la IA al usuario vía WhatsApp Cloud API."""
    wa_token = token or os.environ.get("WHATSAPP_TOKEN", "")
    if not wa_token or not phone_number_id or not to_phone or not text:
        return None
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {wa_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        return res.json()
    except Exception as e:
        print(f"[WhatsApp Cloud API Error] {e}")
        return None


@app.post("/webhook/whatsapp")
async def receive_whatsapp_message(request: Request):
    """
    Webhook Oficial de Meta WhatsApp Cloud API.
    Aislamiento y Enrutamiento Multi-Tenant 100% Automático y Privado:
    1. Identifica el negocio receptor a través del Phone Number ID o número telefónico de soporte en SQLite.
    2. Carga su base de conocimiento, instrucciones personalizadas y catálogo de servicios exclusivos.
    3. Mantiene el hilo y memoria de conversación persistente por cliente.
    4. Envía la respuesta de la IA en tiempo real directamente al chat de WhatsApp del cliente.
    """
    body = await request.json()
    entries = body.get("entry", [])
    responses_log = []

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = str(metadata.get("phone_number_id") or "")
            display_phone = str(metadata.get("display_phone_number") or "")

            # 1. Enrutamiento dinámico al negocio correspondiente
            matched_tenant = None
            if phone_number_id:
                matched_tenant = get_tenant_by_whatsapp(phone_number_id)
            if not matched_tenant and display_phone:
                matched_tenant = get_tenant_by_whatsapp(display_phone)

            # Fallback seguro a Klyven Studio
            tenant_id = matched_tenant.get("tenant_id") if matched_tenant else "KLYVEN-STUDIO"
            tenant_obj = resolve_tenant(tenant_id)

            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            customer_name = ""
            if contacts and len(contacts) > 0:
                customer_name = contacts[0].get("profile", {}).get("name", "")

            for msg in messages:
                sender_id = msg.get("from")  # Número del cliente
                msg_type = msg.get("type")
                user_text = msg.get("text", {}).get("body", "") if msg_type == "text" else ""

                if user_text:
                    # 2. Sesión e historial conversacional aislado por cliente y tenant
                    conv_id = f"wa_{tenant_id}_{sender_id}"
                    history = get_conversation_history(conv_id, limit=8)

                    # Guardar mensaje del usuario en base de datos
                    save_conversation_message(conv_id, tenant_id, "user", user_text)

                    # 3. Generar respuesta contextual con IA
                    result = engine.generate_response(user_text, tenant_obj, history)
                    parsed = result.get("parsed_json", {})
                    bot_reply = parsed.get("mensaje_cliente", "") or "¡Hola! ¿En qué podemos ayudarte hoy?"

                    # Guardar respuesta del bot en base de datos
                    save_conversation_message(conv_id, tenant_id, "assistant", bot_reply, payload=parsed)

                    # 4. Capturar prospecto o reserva si el bot detectó intención
                    try:
                        save_lead(
                            tenant_id=tenant_id,
                            session_id=conv_id,
                            customer_name=customer_name or f"WhatsApp {sender_id}",
                            contact_info=sender_id,
                            service_interest=parsed.get("servicio", ""),
                            notes=f"Mensaje WhatsApp: {user_text[:100]}"
                        )
                    except Exception:
                        pass

                    # 5. Enviar mensaje de vuelta a WhatsApp vía Meta Cloud API
                    tenant_wa_token = None
                    if matched_tenant and matched_tenant.get("config"):
                        tenant_wa_token = matched_tenant["config"].get("whatsapp_token")

                    send_res = send_whatsapp_cloud_reply(
                        phone_number_id=phone_number_id,
                        to_phone=sender_id,
                        text=bot_reply,
                        token=tenant_wa_token
                    )

                    responses_log.append({
                        "tenant_id": tenant_id,
                        "business": tenant_obj.business_name,
                        "sender": sender_id,
                        "customer_name": customer_name,
                        "received": user_text,
                        "bot_reply": bot_reply,
                        "meta_api_result": send_res
                    })

    return {"status": "processed", "replies": responses_log}


# ==============================================================================
# WEBHOOK STRIPE
# ==============================================================================
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.json()
    event_type = payload.get("type")

    if event_type == "checkout.session.completed":
        session = payload.get("data", {}).get("object", {})
        metadata = session.get("metadata", {})

        # 1. Activación de suscripción de bot para el cliente
        sub_tenant_id = metadata.get("tenant_id") or session.get("client_reference_id")
        if sub_tenant_id:
            update_subscription_status(sub_tenant_id, "active")

        # 2. Confirmación de orden de reserva si aplica
        order_id = metadata.get("order_id")
        if order_id:
            confirm_res = confirm_payment(order_id)
            if confirm_res["success"]:
                assign_driver(order_id, confirm_res["order"].get("operational_data", {}), confirm_res["order"].get("tenant_name", ""))
        return {"status": "payment_confirmed", "order_id": order_id, "tenant_activated": sub_tenant_id}

    return {"status": "event_received"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
