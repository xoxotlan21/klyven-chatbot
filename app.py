"""
TravelSales.ai - Plataforma SaaS Multi-Tenant de Comercio Conversacional
Suite completa de Ventas, Cotización, Despacho, Radar de Vuelos, Stripe y WhatsApp.
"""

import json
import os
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from engine import ConversationEngine, DEFAULT_TENANTS, TenantConfig
from services.flight_service import lookup_flight
from services.stripe_service import create_checkout_session, confirm_payment, get_all_orders
from services.dispatch_service import assign_driver, generate_voucher_data, get_all_dispatches, MOCK_DRIVERS
from services.audio_service import transcribe_audio_bytes
from services.pdf_service import generate_voucher_pdf
from services.excel_importer import parse_pricing_csv, generate_sample_pricing_csv, pricing_json_to_csv
from services.geo_service import calculate_route_quote, GEO_LOCATIONS

# Configuración inicial de la página
st.set_page_config(
    page_title="TravelSales.ai | Master Suite SaaS Multi-Tenant",
    page_icon="🛫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS SaaS de alto impacto
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f17;
        color: #e2e8f0;
    }
    
    /* Header principal */
    .status-badge-online {
        display: inline-block;
        padding: 4px 12px;
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid #10b981;
        border-radius: 14px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* Badges FSM */
    .state-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .state-0 { background-color: #3b82f6; color: white; }
    .state-1 { background-color: #f59e0b; color: white; }
    .state-2 { background-color: #8b5cf6; color: white; }
    .state-3 { background-color: #10b981; color: white; }
    .state-4 { background-color: #ef4444; color: white; }

    /* Tarjeta de checkout Stripe */
    .stripe-card {
        background: linear-gradient(135deg, #635bff 0%, #4338ca 100%);
        color: white;
        padding: 18px;
        border-radius: 12px;
        margin: 12px 0;
        box-shadow: 0 8px 24px rgba(99, 91, 255, 0.25);
    }
    .stripe-card h4 {
        margin: 0 0 8px 0;
        color: white;
    }
    .stripe-btn {
        display: inline-block;
        background-color: #ffffff;
        color: #4338ca !important;
        font-weight: bold;
        padding: 10px 22px;
        border-radius: 8px;
        text-decoration: none;
        margin-top: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }

    /* Voucher de confirmación */
    .voucher-card {
        background-color: #1e293b;
        border: 2px dashed #3b82f6;
        border-radius: 12px;
        padding: 20px;
        margin-top: 15px;
    }

    /* Alerta de escalación */
    .escalation-alert {
        background-color: rgba(239, 68, 68, 0.12);
        border-left: 4px solid #ef4444;
        padding: 14px 18px;
        border-radius: 6px;
        margin: 10px 0;
        color: #fca5a5;
    }

    /* Radar de vuelos */
    .flight-radar-card {
        background-color: #131d2e;
        border: 1px solid #1e3a8a;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)


# Inicialización de estado de sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_tenant_name" not in st.session_state:
    st.session_state.selected_tenant_name = "Traslados Riviera Maya"

if "tenant_configs" not in st.session_state:
    st.session_state.tenant_configs = {name: cfg for name, cfg in DEFAULT_TENANTS.items()}


# ==============================================================================
# SIDEBAR: CONFIGURACIÓN MULTI-TENANT & API KEYS
# ==============================================================================
with st.sidebar:
    st.title("🏢 Panel Multi-Tenant")
    st.caption("Suite Comercial & Operativa SaaS")

    env_api_key = os.environ.get("GEMINI_API_KEY", "")
    api_key_input = st.text_input(
        "🔑 Gemini API Key:",
        value=env_api_key,
        type="password",
        help="Cargada automáticamente desde .env o ingresable aquí.",
        placeholder="AQ.Ab..."
    )

    model_option = st.selectbox(
        "🧠 Modelo de IA:",
        options=["gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-3.8-flash", "gemini-flash-latest"],
        index=0,
        help="gemini-3.1-flash-lite responde en ~1.5s con cero alucinación."
    )

    st.divider()

    st.subheader("Tenant Activo")
    tenant_names = list(st.session_state.tenant_configs.keys())
    selected_name = st.selectbox(
        "Seleccionar Negocio:",
        options=tenant_names,
        index=tenant_names.index(st.session_state.selected_tenant_name)
    )

    if selected_name != st.session_state.selected_tenant_name:
        st.session_state.selected_tenant_name = selected_name
        st.session_state.messages = []
        st.rerun()

    current_tenant = st.session_state.tenant_configs[selected_name]

    with st.expander("⚙️ Parámetros Comerciales", expanded=False):
        edit_name = st.text_input("Nombre Comercial:", value=current_tenant.business_name)
        edit_id = st.text_input("Tenant ID:", value=current_tenant.business_id)
        edit_industry = st.text_input("Industria / Giro:", value=current_tenant.business_industry)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            edit_currency = st.selectbox(
                "Moneda:",
                options=["USD", "MXN", "EUR"],
                index=["USD", "MXN", "EUR"].index(current_tenant.currency) if current_tenant.currency in ["USD", "MXN", "EUR"] else 0
            )
        with col_c2:
            edit_deposit = st.number_input("Anticipo %:", min_value=0, max_value=100, value=current_tenant.deposit_percentage, step=10)

        edit_phone = st.text_input("Teléfono de Despacho:", value=current_tenant.support_phone)
        edit_tone = st.text_area("Estilo y Tono:", value=current_tenant.tone_style, height=68)

    with st.expander("🚐 Catálogo de Flota (CATALOG_JSON)", expanded=False):
        edit_catalog = st.text_area("JSON de Flota:", value=current_tenant.catalog_json, height=180)
        try:
            json.loads(edit_catalog)
            st.success("JSON válido", icon="✅")
        except json.JSONDecodeError as e:
            st.error(f"Error JSON: {e}", icon="⚠️")

    with st.expander("💲 Matriz de Rutas y Precios (PRICING_JSON)", expanded=False):
        edit_pricing = st.text_area("JSON de Precios:", value=current_tenant.pricing_json, height=180)
        try:
            json.loads(edit_pricing)
            st.success("JSON válido", icon="✅")
        except json.JSONDecodeError as e:
            st.error(f"Error JSON: {e}", icon="⚠️")

    with st.expander("📊 Excel / CSV: Subir Tarifas Reales", expanded=False):
        st.caption("Los dueños de negocio pueden gestionar sus precios en Excel sin programar.")
        csv_template = generate_sample_pricing_csv()
        st.download_button("📥 Descargar Plantilla Excel (.csv)", data=csv_template, file_name="plantilla_tarifas.csv", mime="text/csv", use_container_width=True)
        
        uploaded_csv = st.file_uploader("Subir lista de precios (.csv):", type=["csv"], key="pricing_csv_uploader")
        if uploaded_csv:
            csv_text = uploaded_csv.read().decode("utf-8")
            ok, msg, new_pricing = parse_pricing_csv(csv_text)
            if ok:
                st.success(msg, icon="✅")
                edit_pricing = json.dumps(new_pricing, indent=2, ensure_ascii=False)
                current_tenant.pricing_json = edit_pricing
            else:
                st.error(msg, icon="⚠️")

        current_csv = pricing_json_to_csv(edit_pricing)
        st.download_button("📤 Exportar Tarifas a Excel (.csv)", data=current_csv, file_name=f"tarifas_{current_tenant.business_id}.csv", mime="text/csv", use_container_width=True)

    # Guardar cambios
    st.session_state.tenant_configs[selected_name] = TenantConfig(
        business_id=edit_id,
        business_name=edit_name,
        business_industry=edit_industry,
        currency=edit_currency,
        support_phone=edit_phone,
        tone_style=edit_tone,
        deposit_percentage=int(edit_deposit),
        cancellation_policy=current_tenant.cancellation_policy,
        flight_delay_policy=current_tenant.flight_delay_policy,
        extra_policy=current_tenant.extra_policy,
        legal_requirements=current_tenant.legal_requirements,
        catalog_json=edit_catalog,
        pricing_json=edit_pricing
    )

    st.divider()

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Nuevo Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    with col_btn2:
        session_json = json.dumps(st.session_state.messages, indent=2, ensure_ascii=False)
        st.download_button(
            "💾 Exportar",
            data=session_json,
            file_name=f"chat_{current_tenant.business_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )


# ==============================================================================
# HEADER DE LA PLATAFORMA
# ==============================================================================
active_tenant = st.session_state.tenant_configs[st.session_state.selected_tenant_name]

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 10px;">
        <h2 style="margin: 0;">{active_tenant.business_name}</h2>
        <span class="status-badge-online">🟢 En Línea (~1.5s)</span>
    </div>
    <div style="margin-top: 4px; color: #94a3b8; font-size: 0.9rem;">
        Tenant: <code>{active_tenant.business_id}</code> | Moneda: <b>{active_tenant.currency}</b> | Anticipo: <b>{active_tenant.deposit_percentage}%</b> | Contacto: <b>{active_tenant.support_phone}</b>
    </div>
    """, unsafe_allow_html=True)

with col_h2:
    st.metric(label="Mensajes en Sesión", value=len(st.session_state.messages))

st.divider()


# ==============================================================================
# TABS PRINCIPALES DE LA PLATAFORMA SAAS
# ==============================================================================
tab_chat, tab_flight, tab_stripe, tab_dispatch, tab_analytics, tab_webhooks = st.tabs([
    "💬 Chat Comercial & Ventas",
    "✈️ Radar de Vuelos en Vivo",
    "💳 Pasarela Stripe & Vouchers",
    "🚖 Despacho de Choferes",
    "📊 Analítica SaaS",
    "🌐 Webhooks WhatsApp & API"
])


def get_state_badge_html(state_str: str) -> str:
    css_class = "state-0"
    if "ESTADO_1" in state_str:
        css_class = "state-1"
    elif "ESTADO_2" in state_str:
        css_class = "state-2"
    elif "ESTADO_3" in state_str:
        css_class = "state-3"
    elif "ESTADO_4" in state_str:
        css_class = "state-4"
    return f'<span class="state-badge {css_class}">{state_str}</span>'


# ------------------------------------------------------------------------------
# TAB 1: CHAT COMERCIAL & VENTAS
# ------------------------------------------------------------------------------
with tab_chat:
    # Atajos de simulación rápida
    with st.container():
        st.caption("💡 Atajos de simulación rápida:")
        c1, c2, c3, c4 = st.columns(4)
        quick_input = None
        with c1:
            if st.button("1. Saludo Inicial", use_container_width=True):
                quick_input = "Hola buenas tardes, ¿qué servicios tienen disponibles?"
        with c2:
            if st.button("2. Cotizar Trayecto", use_container_width=True):
                if "Riviera" in active_tenant.business_name:
                    quick_input = "Necesito un traslado del Aeropuerto de Cancún a Akumal para 5 personas el 15 de noviembre llegando en el vuelo AM 402."
                elif "Cabos" in active_tenant.business_name:
                    quick_input = "Necesito traslado desde el Aeropuerto SJD hacia Cabo San Lucas Marina para 4 personas el 15 de noviembre."
                else:
                    quick_input = "Requiero traslado del AICM T2 a Paseo de la Reforma para 3 personas con 3 maletas el 18 de noviembre a las 17:00."
        with c3:
            if st.button("3. Objeción Precio", use_container_width=True):
                quick_input = "¿Por qué tan caro comparado con un taxi tradicional? ¿Tienen algún descuento?"
        with c4:
            if st.button("4. Cierre y Pago", use_container_width=True):
                quick_input = "Me parece perfecto el precio y las condiciones. ¿Cómo le hacemos para apartar y pagar de una vez?"

    # Uploader de notas de voz / audio
    with st.expander("🎙️ Simular Nota de Voz de WhatsApp (Audio a Texto)", expanded=False):
        uploaded_audio = st.file_uploader("Sube una nota de voz (.mp3, .wav, .ogg, .m4a):", type=["mp3", "wav", "ogg", "m4a"])
        if uploaded_audio and st.button("Transcribir y Procesar Audio"):
            with st.spinner("Transcribiendo audio con Gemini Multimodal..."):
                trans_res = transcribe_audio_bytes(uploaded_audio.read(), mime_type=uploaded_audio.type or "audio/mp3", api_key=api_key_input)
                if trans_res["success"]:
                    st.success(f"🗣️ Transcripción: \"{trans_res['transcription']}\"")
                    quick_input = trans_res["transcription"]
                else:
                    st.error(f"Error de transcripción: {trans_res['error']}")

    st.write("")

    # Historial de mensajes
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(msg["content"])

                payload = msg.get("payload", {})
                control_flujo = payload.get("control_flujo", {})
                motor_precios = payload.get("motor_precios", {})
                datos_operativos = payload.get("datos_operativos", {})
                stripe_url = msg.get("stripe_url")

                # Tarjeta Stripe si es cierre
                if control_flujo.get("accion_backend") == "GENERAR_CHECKOUT_STRIPE":
                    total_val = motor_precios.get("precio_total") or 0.0
                    moneda_val = motor_precios.get("moneda") or active_tenant.currency
                    sku_val = datos_operativos.get("id_sku_seleccionado") or "RESERVA-CONFIRMADA"
                    url_to_use = stripe_url or "#"

                    st.markdown(f"""
                    <div class="stripe-card">
                        <h4>💳 Checkout Seguro Generado (Stripe Connect)</h4>
                        <div><b>Comercio:</b> {active_tenant.business_name} (ID: {active_tenant.business_id})</div>
                        <div><b>Servicio / Unidad:</b> {sku_val}</div>
                        <div style="font-size: 1.25rem; font-weight: bold; margin-top: 6px;">
                            Monto a pagar: ${total_val:,.2f} {moneda_val}
                        </div>
                        <a href="{url_to_use}" target="_blank" class="stripe-btn">Pagar con Stripe Checkout 🔒</a>
                    </div>
                    """, unsafe_allow_html=True)

                elif control_flujo.get("accion_backend") == "AVISAR_OPERADOR_HUMANO":
                    motivo = control_flujo.get("motivo_bloqueo_o_escalacion") or "Atención manual requerida."
                    st.markdown(f"""
                    <div class="escalation-alert">
                        <b>⚠️ Transferencia a Despacho Humano</b><br>
                        Motivo: <i>{motivo}</i><br>
                        Línea de soporte directo: <b>{active_tenant.support_phone}</b>
                    </div>
                    """, unsafe_allow_html=True)

                # Telemetría expandible
                metadata = payload.get("metadata", {})
                estado_actual = metadata.get("estado_conversacion", "ESTADO_DESCONOCIDO")
                with st.expander(f"🔍 Telemetría & Payload JSON del Backend [{estado_actual}]"):
                    st.markdown(get_state_badge_html(estado_actual), unsafe_allow_html=True)
                    c_col1, c_col2, c_col3 = st.columns(3)
                    with c_col1:
                        st.markdown("**Metadatos FSM**")
                        st.write(f"- Intención: `{metadata.get('intencion_primaria')}`")
                        st.write(f"- Confianza: `{metadata.get('confianza_clasificacion')}`")
                        st.write(f"- Idioma: `{metadata.get('idioma_cliente')}`")
                    with c_col2:
                        st.markdown("**Motor de Precios**")
                        st.write(f"- Total: `{motor_precios.get('precio_total')} {motor_precios.get('moneda')}`")
                        st.write(f"- Cotización Manual: `{motor_precios.get('requiere_cotizacion_manual')}`")
                    with c_col3:
                        st.markdown("**Control de Flujo**")
                        st.write(f"- Acción: `{control_flujo.get('accion_backend')}`")
                        st.write(f"- Pendientes: `{control_flujo.get('campos_pendientes')}`")

                    st.markdown("**Datos Operativos Recopilados:**")
                    st.json(datos_operativos)

    # Chat Input
    user_prompt = st.chat_input("Escribe tu consulta como cliente o turista...")
    if quick_input and not user_prompt:
        user_prompt = quick_input

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user", avatar="👤"):
            st.write(user_prompt)

        engine = ConversationEngine(api_key=api_key_input, model_name=model_option)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Procesando con motor de ventas..."):
                result = engine.generate_response(
                    user_message=user_prompt,
                    tenant=active_tenant,
                    conversation_history=st.session_state.messages[:-1]
                )

            parsed_json = result.get("parsed_json", {})
            cliente_msg = parsed_json.get("mensaje_cliente", "Gracias por tu mensaje.")
            stripe_link = result.get("stripe_url")

            st.write(cliente_msg)

            control_flujo = parsed_json.get("control_flujo", {})
            motor_precios = parsed_json.get("motor_precios", {})
            datos_operativos = parsed_json.get("datos_operativos", {})

            # Si es checkout de Stripe, registrar en base de datos de órdenes
            if control_flujo.get("accion_backend") == "GENERAR_CHECKOUT_STRIPE":
                total_val = motor_precios.get("precio_total") or 0.0
                moneda_val = motor_precios.get("moneda") or active_tenant.currency
                sku_val = datos_operativos.get("id_sku_seleccionado") or "RESERVA-CONFIRMADA"

                # Crear orden formal en servicio de Stripe
                checkout_record = create_checkout_session(
                    tenant_id=active_tenant.business_id,
                    tenant_name=active_tenant.business_name,
                    amount=total_val,
                    currency=moneda_val,
                    service_name=sku_val,
                    operational_data=datos_operativos
                )
                stripe_link = checkout_record["checkout_url"]

                st.markdown(f"""
                <div class="stripe-card">
                    <h4>💳 Checkout Seguro Generado (Stripe Connect)</h4>
                    <div><b>Comercio:</b> {active_tenant.business_name} (ID: {active_tenant.business_id})</div>
                    <div><b>Orden ID:</b> <code>{checkout_record['order_id']}</code> | <b>Servicio:</b> {sku_val}</div>
                    <div style="font-size: 1.25rem; font-weight: bold; margin-top: 6px;">
                        Monto a pagar: ${total_val:,.2f} {moneda_val}
                    </div>
                    <a href="{stripe_link}" target="_blank" class="stripe-btn">Pagar con Stripe Checkout 🔒</a>
                </div>
                """, unsafe_allow_html=True)

            elif control_flujo.get("accion_backend") == "AVISAR_OPERADOR_HUMANO":
                motivo = control_flujo.get("motivo_bloqueo_o_escalacion") or "Atención manual requerida."
                st.markdown(f"""
                <div class="escalation-alert">
                    <b>⚠️ Transferencia a Despacho Humano</b><br>
                    Motivo: <i>{motivo}</i><br>
                    Línea de soporte directo: <b>{active_tenant.support_phone}</b>
                </div>
                """, unsafe_allow_html=True)

            # Telemetría expandible
            metadata = parsed_json.get("metadata", {})
            estado_actual = metadata.get("estado_conversacion", "ESTADO_DESCONOCIDO")
            with st.expander(f"🔍 Telemetría & Payload JSON del Backend [{estado_actual}]"):
                st.markdown(get_state_badge_html(estado_actual), unsafe_allow_html=True)
                c_col1, c_col2, c_col3 = st.columns(3)
                with c_col1:
                    st.markdown("**Metadatos FSM**")
                    st.write(f"- Intención: `{metadata.get('intencion_primaria')}`")
                    st.write(f"- Confianza: `{metadata.get('confianza_clasificacion')}`")
                    st.write(f"- Idioma: `{metadata.get('idioma_cliente')}`")
                with c_col2:
                    st.markdown("**Motor de Precios**")
                    st.write(f"- Total: `{motor_precios.get('precio_total')} {motor_precios.get('moneda')}`")
                    st.write(f"- Cotización Manual: `{motor_precios.get('requiere_cotizacion_manual')}`")
                with c_col3:
                    st.markdown("**Control de Flujo**")
                    st.write(f"- Acción: `{control_flujo.get('accion_backend')}`")
                    st.write(f"- Pendientes: `{control_flujo.get('campos_pendientes')}`")

                st.markdown("**Datos Operativos Recopilados:**")
                st.json(datos_operativos)

            st.session_state.messages.append({
                "role": "assistant",
                "content": cliente_msg,
                "payload": parsed_json,
                "stripe_url": stripe_link
            })


# ------------------------------------------------------------------------------
# TAB 2: RADAR DE VUELOS EN VIVO
# ------------------------------------------------------------------------------
with tab_flight:
    st.subheader("✈️ Monitoreo de Vuelos en Tiempo Real")
    st.caption("Verificación automática de itinerarios, puertas y retrasos para despacho puntual.")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        flight_query = st.text_input("Número de Vuelo (ej. AM 402, VB 1024, Y4 850, UA 1450, AA 2230):", value="AM 402")
    with col_f2:
        dest_airport = st.selectbox("Aeropuerto Destino:", options=["CUN (Cancún)", "SJD (Los Cabos)", "MEX (AICM CDMX)", "NLU (AIFA)"], index=0)

    if st.button("🔎 Consultar Telemetría del Vuelo"):
        with st.spinner("Rastreando vuelo en radar..."):
            flight_info = lookup_flight(flight_query, dest_airport.split()[0])
            st.session_state.last_flight_info = flight_info

    if "last_flight_info" in st.session_state:
        info = st.session_state.last_flight_info
        st.markdown(f"""
        <div class="flight-radar-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #60a5fa;">✈️ {info['airline']} ({info['flight_code']})</h3>
                <span class="status-badge-online" style="border-color: {'#ef4444' if info['has_delay'] else '#10b981'}; color: {'#f87171' if info['has_delay'] else '#34d399'};">
                    {info['status']}
                </span>
            </div>
            <div style="margin-top: 10px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                <div><b>Origen:</b> {info['origin']}</div>
                <div><b>Destino:</b> {info['destination']}</div>
                <div><b>Llegada Estimada:</b> <span style="font-size: 1.1rem; color: #fbbf24;">{info['estimated_arrival']}</span></div>
                <div><b>Terminal Asignada:</b> {info['terminal']}</div>
                <div><b>Puerta de Salida:</b> {info['gate']}</div>
                <div><b>Banda de Equipaje:</b> {info['baggage_belt']}</div>
            </div>
            <div style="margin-top: 14px; padding: 10px; background-color: #1e293b; border-radius: 6px;">
                <b>📋 Recomendación Automática para Despacho:</b><br>
                <i>{info['recomendacion_chofer']}</i>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("🗺️ Calculadora Geográfica de Carreteras y Rutas")
    st.caption("Cálculo matemático de distancias reales en km y cotizaciones dinámicas para traslados fuera de catálogo.")

    col_geo1, col_geo2 = st.columns(2)
    with col_geo1:
        geo_orig = st.selectbox("Punto de Partida:", options=list(GEO_LOCATIONS.keys()), index=0)
    with col_geo2:
        geo_dest = st.selectbox("Punto de Llegada:", options=list(GEO_LOCATIONS.keys()), index=6)

    if st.button("🛣️ Calcular Kilómetros Reales y Cotizar"):
        quote = calculate_route_quote(geo_orig, geo_dest, currency=active_tenant.currency)
        st.success(f"Distancia real de carretera: **{quote['distance_km']} km** | Tiempo estimado: **{quote['estimated_duration']}**")
        st.info(f"Tarifa dinámica calculada: **${quote['calculated_price']:,.2f} {quote['currency']}** (Sencillo) / **${quote['roundtrip_price']:,.2f} {quote['currency']}** (Redondo)")
        st.caption(f"Fórmula: {quote['breakdown']}")


# ------------------------------------------------------------------------------
# TAB 3: PASARELA STRIPE & VOUCHERS
# ------------------------------------------------------------------------------
with tab_stripe:
    st.subheader("💳 Órdenes y Checkout de Stripe")
    st.caption("Registro de pagos procesados y emisión instantánea de vouchers con código QR.")

    orders = get_all_orders()
    if not orders:
        st.info("Aún no se han generado órdenes en esta sesión. Completa una cotización en el chat para disparar un checkout.")
    else:
        for ord_data in orders:
            col_o1, col_o2, col_o3 = st.columns([2, 1, 1])
            with col_o1:
                st.markdown(f"**Orden:** ` {ord_data['order_id']} ` | **Servicio:** {ord_data['service_name']}")
                st.caption(f"Creada: {ord_data['created_at'][:19]} | Comercio: {ord_data['tenant_name']}")
            with col_o2:
                st.markdown(f"**Monto:** ${ord_data['amount']:,.2f} {ord_data['currency']}")
                badge_color = "green" if ord_data['status'] == "PAGADO_CONFIRMADO" else "orange"
                st.markdown(f"Estado: :{badge_color}[{ord_data['status']}]")
            with col_o3:
                if ord_data['status'] != "PAGADO_CONFIRMADO":
                    if st.button("✅ Confirmar Pago", key=f"pay_{ord_data['order_id']}"):
                        confirm_payment(ord_data['order_id'])
                        assign_driver(ord_data['order_id'], ord_data['operational_data'], ord_data['tenant_name'])
                        st.rerun()
                else:
                    if st.button("🎟️ Ver Voucher", key=f"vch_{ord_data['order_id']}"):
                        st.session_state.selected_voucher_order = ord_data

            st.divider()

    # Vista previa de Voucher
    if "selected_voucher_order" in st.session_state:
        vch_order = st.session_state.selected_voucher_order
        vch = generate_voucher_data(vch_order)
        st.markdown(f"""
        <div class="voucher-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #38bdf8;">🎫 VOUCHER OFICIAL DE TRASLADO</h3>
                <span style="font-weight: bold; color: #34d399;">PAGO CONFIRMADO</span>
            </div>
            <div style="margin-top: 10px; display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
                <div>
                    <div><b>Código de Reserva:</b> <code style="font-size: 1.1rem;">{vch['booking_code']}</code></div>
                    <div><b>Comercio Operador:</b> {vch['tenant_name']}</div>
                    <div><b>Servicio:</b> {vch['service_name']}</div>
                    <div><b>Ruta:</b> {vch['origin']} ➡️ {vch['destination']}</div>
                    <div><b>Fecha y Hora:</b> {vch['date']} a las {vch['time']} hrs</div>
                    <div><b>Pasajeros:</b> {vch['passengers']} | <b>Vuelo:</b> {vch['flight_number']}</div>
                    <div><b>Chofer Asignado:</b> {vch['driver_name']} ({vch['driver_phone']})</div>
                    <div style="margin-top: 8px; font-size: 1.1rem; color: #a3e635;"><b>Monto Total Pagado:</b> ${vch['amount_paid']:,.2f} {vch['currency']}</div>
                </div>
                <div style="text-align: center;">
                    <img src="{vch['qr_code_url']}" width="140" style="border-radius: 8px; background: white; padding: 4px;"/><br>
                    <small style="color: #94a3b8;">Escanear para verificar pase</small>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Generación de PDF real descargable con ReportLab
        pdf_bytes = generate_voucher_pdf(vch_order, vch['tenant_name'])
        st.download_button(
            "📥 Descargar Voucher Oficial en PDF (Formato de Impresión)",
            data=pdf_bytes,
            file_name=f"Voucher_{vch_order['order_id']}.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# ------------------------------------------------------------------------------
# TAB 4: DESPACHO DE CHOFERES
# ------------------------------------------------------------------------------
with tab_dispatch:
    st.subheader("🚖 Centro de Despacho y Asignación de Conductores")
    st.caption("Notificaciones automáticas generadas para la cuadrilla de conductores.")

    col_d1, col_d2 = st.columns([1, 2])
    with col_d1:
        st.markdown("### Choferes Registrados")
        for drv in MOCK_DRIVERS:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 10px; border-radius: 8px; margin-bottom: 8px;">
                <b>{drv['name']}</b> ⭐ {drv['rating']}<br>
                <small>{drv['vehicle']}</small><br>
                <small>Tel: {drv['phone']}</small>
            </div>
            """, unsafe_allow_html=True)

    with col_d2:
        st.markdown("### Registro de Alertas Enviadas al Grupo")
        dispatches = get_all_dispatches()
        if not dispatches:
            st.info("No hay despachos emitidos aún. Se generarán automáticamente al confirmarse un pago.")
        else:
            for dsp in dispatches:
                st.code(dsp['message'], language="markdown")


# ------------------------------------------------------------------------------
# TAB 5: ANALÍTICA SAAS
# ------------------------------------------------------------------------------
with tab_analytics:
    st.subheader("📊 Métricas de Conversión y Rendimiento del Negocio")
    st.caption("Telemetría en tiempo real de ingresos y efectividad del bot.")

    all_orders = get_all_orders()
    total_sales = sum(o["amount"] for o in all_orders if o["status"] == "PAGADO_CONFIRMADO")
    total_orders_count = len(all_orders)
    paid_count = sum(1 for o in all_orders if o["status"] == "PAGADO_CONFIRMADO")
    conv_rate = (paid_count / total_orders_count * 100) if total_orders_count > 0 else 0.0

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Ingresos Totales", f"${total_sales:,.2f} {active_tenant.currency}")
    with col_m2:
        st.metric("Checkouts Generados", total_orders_count)
    with col_m3:
        st.metric("Reservas Pagadas", paid_count)
    with col_m4:
        st.metric("Tasa de Cierre", f"{conv_rate:.1f}%")

    st.divider()
    st.markdown("### 👥 Prospectos Calificados Capturados (CRM)")
    from services.crm_service import get_all_leads, export_leads_to_csv
    leads_list = get_all_leads(active_tenant.business_id)
    if not leads_list:
        st.info("No hay prospectos capturados aún para este negocio.")
    else:
        st.dataframe(leads_list, use_container_width=True)
        csv_leads = export_leads_to_csv(active_tenant.business_id)
        st.download_button(
            "📥 Descargar Base de Prospectos en Excel (CSV)",
            data=csv_leads,
            file_name=f"leads_{active_tenant.business_id}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )


# ------------------------------------------------------------------------------
# TAB 6: WEBHOOKS WHATSAPP & API GATEWAY
# ------------------------------------------------------------------------------
with tab_webhooks:
    st.subheader("🌐 Conexión con Meta WhatsApp Cloud API & Webhooks")
    st.caption("Endpoints listos para vincular con Meta Developer Console y Stripe.")

    st.markdown("""
    Para conectar tu número de WhatsApp Business oficial con este bot:
    1. Dirígete a [developers.facebook.com](https://developers.facebook.com/) y crea una app tipo **WhatsApp**.
    2. En el menú **WhatsApp > Configuration**, ingresa la URL de webhook:
       * **Callback URL:** `https://tu-dominio.com/webhook/whatsapp`
       * **Verify Token:** `travelsales_secret_verify_token`
    3. Suscribe los campos de webhook: `messages`.
    """)

    st.markdown("### Endpoints Expuestos por `server.py`:")
    st.code("""
# Handshake de verificación de Meta:
GET  http://localhost:8000/webhook/whatsapp

# Recepción de mensajes y audios de WhatsApp:
POST http://localhost:8000/webhook/whatsapp

# Confirmación de pagos de Stripe:
POST http://localhost:8000/webhook/stripe
    """, language="bash")

    st.markdown("### Comando para ejecutar el servidor Webhook en segundo plano:")
    st.code("python3 server.py", language="bash")
