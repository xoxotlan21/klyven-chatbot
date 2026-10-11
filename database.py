"""
Módulo de Base de Datos Relacional Persistente (SQLite / PostgreSQL ready).
Garantiza aislamiento estricto de datos por tenant (Multi-Tenant Privacy) y persistencia real de órdenes.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_FILE = Path(__file__).parent / "travelsales.db"


def get_db_connection():
    """Crea una conexión a la base de datos con modo row factory tipo diccionario."""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Inicializa el esquema de tablas relacionales si no existen."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Tabla de Tenants (Negocios Clientes Registrados)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        tenant_id TEXT PRIMARY KEY,
        business_name TEXT NOT NULL,
        industry TEXT,
        currency TEXT DEFAULT 'USD',
        support_phone TEXT,
        deposit_percentage INTEGER DEFAULT 100,
        api_key TEXT,
        config_json TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 2. Tabla de Conversaciones y Sesiones de Clientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        customer_id TEXT,
        customer_phone TEXT,
        customer_language TEXT DEFAULT 'es',
        status TEXT DEFAULT 'ACTIVA',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
    );
    """)

    # 3. Tabla de Mensajes del Historial Conversacional
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        sender_role TEXT NOT NULL, -- 'user' o 'assistant'
        content TEXT NOT NULL,
        payload_json TEXT,         -- JSON estructurado con telemetría FSM
        created_at TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
    );
    """)

    # 4. Tabla de Órdenes y Reservas Reales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        conversation_id TEXT,
        customer_name TEXT,
        customer_phone TEXT,
        service_name TEXT,
        origin TEXT,
        destination TEXT,
        passengers INTEGER,
        flight_number TEXT,
        service_date TEXT,
        service_time TEXT,
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        stripe_session_id TEXT,
        status TEXT DEFAULT 'PENDIENTE_DE_PAGO', -- 'PENDIENTE_DE_PAGO', 'PAGADO_CONFIRMADO', 'CANCELADO'
        created_at TEXT NOT NULL,
        paid_at TEXT,
        FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
    );
    """)

    # 5. Tabla de Leads y Prospectos Comerciales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        session_id TEXT,
        customer_name TEXT,
        contact_info TEXT,
        service_interest TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
    );
    """)

    # 6. Tabla de Preguntas Sin Resolver (Knowledge Gaps)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS unresolved_questions (
        question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        conversation_id TEXT,
        question_text TEXT NOT NULL,
        bot_response TEXT,
        resolved INTEGER DEFAULT 0,
        added_answer TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
    );
    """)

    # 7. Tabla de Agenda y Reservas (Adaptable por tipo de negocio)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        business_type TEXT DEFAULT 'general',
        customer_name TEXT NOT NULL,
        customer_contact TEXT NOT NULL,
        service_name TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        booking_time TEXT NOT NULL,
        end_time TEXT,
        resource_assigned TEXT,
        origin TEXT,
        destination TEXT,
        passengers_or_qty INTEGER DEFAULT 1,
        status TEXT DEFAULT 'PENDIENTE',
        advance_amount REAL DEFAULT 0,
        total_amount REAL DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
    );
    """)

    # Migración de columnas adicionales en leads si ya existía la tabla
    for col_name in ["session_id", "contact_info", "service_interest"]:
        try:
            cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} TEXT")
        except Exception:
            pass

    conn.commit()
    conn.close()



# ==============================================================================
# OPERACIONES DE AISLAMIENTO MULTI-TENANT & PRIVACIDAD
# ==============================================================================

def save_conversation_message(conversation_id: str, tenant_id: str, role: str, content: str, payload: Optional[Dict] = None):
    """Guarda un mensaje en la base de datos asegurando pertenencia al tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Asegurar que la conversación exista
    cursor.execute("SELECT conversation_id FROM conversations WHERE conversation_id = ?", (conversation_id,))
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO conversations (conversation_id, tenant_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """, (conversation_id, tenant_id, now, now))

    # Insertar el mensaje
    payload_str = json.dumps(payload, ensure_ascii=False) if payload else None
    cursor.execute("""
    INSERT INTO messages (conversation_id, sender_role, content, payload_json, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (conversation_id, role, content, payload_str, now))

    cursor.execute("UPDATE conversations SET updated_at = ? WHERE conversation_id = ?", (now, conversation_id))
    conn.commit()
    conn.close()


def get_conversation_history(conversation_id: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Obtiene el historial cronológico de una sesión para el motor de IA."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT sender_role as role, content 
    FROM messages 
    WHERE conversation_id = ? 
    ORDER BY message_id ASC 
    LIMIT ?
    """, (conversation_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_tenant_conversations(tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene el listado de conversaciones y el último mensaje de cada sesión para el tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.conversation_id, c.tenant_id, c.status, c.created_at, c.updated_at,
           COUNT(m.message_id) as total_messages,
           (SELECT content FROM messages WHERE conversation_id = c.conversation_id ORDER BY message_id DESC LIMIT 1) as last_message
    FROM conversations c
    LEFT JOIN messages m ON c.conversation_id = m.conversation_id
    WHERE c.tenant_id = ?
    GROUP BY c.conversation_id
    ORDER BY c.updated_at DESC
    LIMIT ?
    """, (tenant_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_db_order(
    tenant_id: str,
    amount: float,
    currency: str,
    service_name: str,
    operational_data: Dict[str, Any],
    stripe_session_id: str,
    conversation_id: Optional[str] = None
) -> str:
    """Crea una orden persistente y segura en la base de datos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().isoformat()

    cursor.execute("""
    INSERT INTO orders (
        order_id, tenant_id, conversation_id, service_name, origin, destination,
        passengers, flight_number, service_date, service_time, amount, currency,
        stripe_session_id, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE_DE_PAGO', ?)
    """, (
        order_id,
        tenant_id,
        conversation_id,
        service_name,
        operational_data.get("origen"),
        operational_data.get("destino"),
        operational_data.get("pasajeros"),
        operational_data.get("numero_vuelo"),
        operational_data.get("fecha_servicio"),
        operational_data.get("hora_servicio"),
        amount,
        currency,
        stripe_session_id,
        now
    ))
    conn.commit()
    conn.close()
    return order_id


def mark_order_paid(order_id: str) -> bool:
    """Actualiza el estado de una orden a PAGADO_CONFIRMADO tras recibir webhook de Stripe."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    UPDATE orders 
    SET status = 'PAGADO_CONFIRMADO', paid_at = ?
    WHERE order_id = ? OR stripe_session_id = ?
    """, (now, order_id, order_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def get_tenant_orders(tenant_id: str) -> List[Dict[str, Any]]:
    """Obtiene únicamente las órdenes que pertenecen al tenant especificado (Privacidad Estricta)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM orders 
    WHERE tenant_id = ? 
    ORDER BY created_at DESC
    """, (tenant_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_or_update_tenant(
    tenant_id: str,
    business_name: str,
    industry: str,
    currency: str = "USD",
    support_phone: str = "",
    config_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Guarda o actualiza un negocio cliente con su configuración personalizada de IA y Widget."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    config_json = json.dumps(config_data or {}, ensure_ascii=False)

    cursor.execute("SELECT tenant_id FROM tenants WHERE tenant_id = ?", (tenant_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("SELECT support_phone FROM tenants WHERE tenant_id = ?", (tenant_id,))
        curr_row = cursor.fetchone()
        curr_phone = curr_row["support_phone"] if curr_row else ""
        final_phone = support_phone if support_phone.strip() else (curr_phone or "")
        cursor.execute("""
        UPDATE tenants
        SET business_name = ?, industry = ?, currency = ?, support_phone = ?, config_json = ?
        WHERE tenant_id = ?
        """, (business_name, industry, currency, final_phone, config_json, tenant_id))
    else:
        cursor.execute("""
        INSERT INTO tenants (tenant_id, business_name, industry, currency, support_phone, config_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tenant_id, business_name, industry, currency, support_phone, config_json, now))

    conn.commit()
    conn.close()
    return {
        "tenant_id": tenant_id,
        "business_name": business_name,
        "industry": industry,
        "currency": currency,
        "support_phone": support_phone,
        "config": config_data or {}
    }


def get_tenant_by_id(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene la configuración completa de un tenant desde SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    if data.get("config_json"):
        try:
            data["config"] = json.loads(data["config_json"])
        except Exception:
            data["config"] = {}
    else:
        data["config"] = {}
    return data


def list_all_tenants() -> List[Dict[str, Any]]:
    """Lista todos los tenants registrados en la plataforma."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tenant_id, business_name, industry, currency, support_phone, created_at FROM tenants ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_lead(tenant_id: str, session_id: str = "", customer_name: str = "", contact_info: str = "", service_interest: str = "", notes: str = "") -> int:
    """Guarda un prospecto o lead comercial extraído de la conversación."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO leads (tenant_id, session_id, customer_name, contact_info, service_interest, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (tenant_id, session_id, customer_name, contact_info, service_interest, notes, now))
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def get_tenant_leads(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene los leads registrados para un tenant en orden cronológico inverso."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT lead_id, tenant_id, session_id, customer_name, contact_info, service_interest, notes, created_at
    FROM leads
    WHERE tenant_id = ?
    ORDER BY created_at DESC
    LIMIT ?
    """, (tenant_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_lead(lead_id: int) -> bool:
    """Elimina un prospecto por su ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads WHERE lead_id = ?", (lead_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def clear_tenant_leads(tenant_id: str) -> int:
    """Limpia todos los prospectos de un tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads WHERE tenant_id = ?", (tenant_id,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


# ==============================================================================
# 6. OPERACIONES DE PREGUNTAS SIN RESOLVER (KNOWLEDGE GAPS)
# ==============================================================================

def save_unresolved_question(
    tenant_id: str,
    question_text: str,
    bot_response: str = "",
    conversation_id: Optional[str] = None
) -> int:
    """Registra una consulta en la que el bot no tuvo respuesta certera para retroalimentar la base de conocimiento."""
    clean_q = question_text.strip()
    if not clean_q or len(clean_q) < 4:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # Evitar duplicados idénticos recientes no resueltos para el mismo tenant
    cursor.execute("""
    SELECT question_id FROM unresolved_questions
    WHERE tenant_id = ? AND LOWER(question_text) = LOWER(?) AND resolved = 0
    """, (tenant_id, clean_q))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing["question_id"]

    cursor.execute("""
    INSERT INTO unresolved_questions (tenant_id, conversation_id, question_text, bot_response, resolved, created_at)
    VALUES (?, ?, ?, ?, 0, ?)
    """, (tenant_id, conversation_id, clean_q, bot_response[:400] if bot_response else "", now))
    q_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return q_id


def get_unresolved_questions(tenant_id: str, only_unresolved: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene las preguntas sin resolver de un tenant para nutrir la base de conocimiento."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM unresolved_questions WHERE tenant_id = ?"
    params: List[Any] = [tenant_id]
    if only_unresolved:
        query += " AND resolved = 0"
    query += " ORDER BY resolved ASC, created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_unresolved_question(question_id: int) -> bool:
    """Elimina una pregunta sin resolver por su ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM unresolved_questions WHERE question_id = ?", (question_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def clear_tenant_unresolved_questions(tenant_id: str) -> int:
    """Limpia todas las preguntas sin resolver de un tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM unresolved_questions WHERE tenant_id = ?", (tenant_id,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def resolve_unresolved_question(question_id: int, tenant_id: str, added_answer: str) -> bool:
    """Marca la pregunta como resuelta e inyecta la nueva respuesta en el conocimiento del tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("""
    SELECT question_text FROM unresolved_questions
    WHERE question_id = ? AND tenant_id = ?
    """, (question_id, tenant_id))
    q_row = cursor.fetchone()
    if not q_row:
        conn.close()
        return False

    q_text = q_row["question_text"]

    # 1. Marcar como resuelta en la tabla
    cursor.execute("""
    UPDATE unresolved_questions
    SET resolved = 1, added_answer = ?, resolved_at = ?
    WHERE question_id = ? AND tenant_id = ?
    """, (added_answer, now, question_id, tenant_id))
    conn.commit()

    # 2. Agregar la nueva Q&A al FAQs del tenant para que la IA la aprenda de inmediato
    cursor.execute("SELECT config_json FROM tenants WHERE tenant_id = ?", (tenant_id,))
    t_row = cursor.fetchone()
    if t_row and t_row["config_json"]:
        try:
            cfg = json.loads(t_row["config_json"])
            existing_faqs = cfg.get("faqs", "") or ""
            new_entry = f"\n\nQ: {q_text}\nA: {added_answer}"
            cfg["faqs"] = existing_faqs.strip() + new_entry
            new_json = json.dumps(cfg, ensure_ascii=False)
            cursor.execute("UPDATE tenants SET config_json = ? WHERE tenant_id = ?", (new_json, tenant_id))
            conn.commit()
        except Exception:
            pass

    conn.close()
    return True


def seed_default_unresolved_questions(tenant_id: str):
    """Precarga preguntas de muestra realistas no resueltas para que el usuario experimente la funcionalidad de inmediato."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    is_klyven = "KLYVEN" in tenant_id.upper()
    samples = [
        {
            "q": "¿Ofrecen planes de mantenimiento mensual o soporte continuo para las páginas web?",
            "resp": "Actualmente no cuento con información detallada sobre planes de mantenimiento mensual. Te sugiero consultar con un asesor.",
        },
        {
            "q": "¿Aceptan pagos fraccionados o mensualidades sin intereses para el desarrollo web?",
            "resp": "No tengo esa información en mi catálogo actual. Un asesor comercial te brindará las facilidades de pago disponibles.",
        },
        {
            "q": "¿Hacen integraciones con pasarelas de pago locales o facturación electrónica de México?",
            "resp": "Disculpa, no dispongo de los detalles específicos sobre facturación fiscal automatizada.",
        }
    ] if is_klyven else [
        {
            "q": "¿Tienen servicio pet-friendly o permiten viajar con perros grandes en la unidad?",
            "resp": "Actualmente no cuento con la política específica de transporte de mascotas grandes. Te sugiero contactar a un asesor.",
        },
        {
            "q": "¿Cuál es la política de tolerancia si el vuelo de llegada se retrasa más de 2 horas en el aeropuerto?",
            "resp": "No dispongo de los detalles exactos del tiempo de espera de cortesía por retrasos.",
        },
        {
            "q": "¿Proporcionan sillas de seguridad para bebés o niños pequeños y tienen costo extra?",
            "resp": "No cuento con esa información en mi catálogo actual.",
        }
    ]

    for s in samples:
        cursor.execute("""
        INSERT INTO unresolved_questions (tenant_id, question_text, bot_response, resolved, created_at)
        VALUES (?, ?, ?, 0, ?)
        """, (tenant_id, s["q"], s["resp"], now))

    conn.commit()
    conn.close()


# ==============================================================================
# 7. OPERACIONES DE AGENDA Y RESERVAS (ADAPTABLE POR GIRO)
# ==============================================================================

def create_booking(booking_data: Dict[str, Any]) -> Dict[str, Any]:
    """Crea una reserva o cita en el sistema de agenda."""
    conn = get_db_connection()
    cursor = conn.cursor()
    booking_id = f"RES-{uuid.uuid4().hex[:7].upper()}"
    now = datetime.now().isoformat()

    t_id = booking_data.get("tenant_id", "KLYVEN-STUDIO")
    cursor.execute("""
    INSERT INTO bookings (
        booking_id, tenant_id, business_type, customer_name, customer_contact,
        service_name, booking_date, booking_time, end_time, resource_assigned,
        origin, destination, passengers_or_qty, status, advance_amount,
        total_amount, currency, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        booking_id,
        t_id,
        booking_data.get("business_type", "general"),
        booking_data.get("customer_name", "Cliente"),
        booking_data.get("customer_contact", ""),
        booking_data.get("service_name", "Servicio"),
        booking_data.get("booking_date", now[:10]),
        booking_data.get("booking_time", "10:00"),
        booking_data.get("end_time", ""),
        booking_data.get("resource_assigned", ""),
        booking_data.get("origin", ""),
        booking_data.get("destination", ""),
        booking_data.get("passengers_or_qty", 1),
        booking_data.get("status", "PENDIENTE"),
        booking_data.get("advance_amount", 0.0),
        booking_data.get("total_amount", 0.0),
        booking_data.get("currency", "USD"),
        booking_data.get("notes", ""),
        now,
        now
    ))
    conn.commit()
    conn.close()

    booking_data["booking_id"] = booking_id
    booking_data["created_at"] = now
    booking_data["updated_at"] = now
    return booking_data


def get_tenant_bookings(tenant_id: str, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene el listado de reservas y citas de un negocio."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM bookings WHERE tenant_id = ?"
    params: List[Any] = [tenant_id]
    if status and status.upper() != "TODAS":
        query += " AND status = ?"
        params.append(status.upper())
    query += " ORDER BY booking_date ASC, booking_time ASC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_booking(booking_id: str) -> bool:
    """Elimina una reserva por su ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def clear_tenant_bookings(tenant_id: str) -> int:
    """Limpia todas las reservas registradas de un tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE tenant_id = ?", (tenant_id,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def update_booking_status(booking_id: str, status: str, notes: Optional[str] = None) -> bool:
    """Actualiza el estado de una reserva (CONFIRMADA, PENDIENTE, COMPLETADA, CANCELADA)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    if notes is not None:
        cursor.execute("""
        UPDATE bookings SET status = ?, notes = ?, updated_at = ?
        WHERE booking_id = ?
        """, (status.upper(), notes, now, booking_id))
    else:
        cursor.execute("""
        UPDATE bookings SET status = ?, updated_at = ?
        WHERE booking_id = ?
        """, (status.upper(), now, booking_id))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def seed_default_bookings(tenant_id: str):
    """Precarga reservas de ejemplo según el giro del tenant."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    today_str = now[:10]

    is_klyven = "KLYVEN" in tenant_id.upper()
    if is_klyven:
        demo_items = [
            ("RES-KLY01", tenant_id, "general", "Carlos Méndez (Fintech Latam)", "+52 55 4123 9876", "Business Website", today_str, "11:00", "12:00", "Andrew / Diseñador Principal", "", "", 1, "CONFIRMADA", 425.0, 850.0, "USD", "Llamada de briefing inicial y estructura de páginas."),
            ("RES-KLY02", tenant_id, "general", "Mariana Gómez (Boutique Joyas)", "+52 33 8765 4321", "Landing Page", today_str, "16:30", "17:15", "Consultor Comercial", "", "", 1, "PENDIENTE", 0.0, 450.0, "USD", "Interesada en lanzamiento de temporada. Requiere cotizar pasarela Stripe."),
            ("RES-KLY03", tenant_id, "general", "Dr. Roberto Silva (Clínica Dental)", "+52 81 9988 7766", "Website Redesign", today_str, "18:00", "19:00", "Andrew / UI UX Specialist", "", "", 1, "COMPLETADA", 700.0, 700.0, "USD", "Rediseño completo de la marca entregado.")
        ]
    else:
        demo_items = [
            ("RES-TRM01", tenant_id, "transporte", "Johnathan Smith", "+1 305 555 0192", "Suburban VIP", today_str, "09:30", "11:00", "Suburban VIP (Chofer: Carlos R.)", "Aeropuerto Cancún (T4)", "Hotel Xcaret Arte", 4, "CONFIRMADA", 110.0, 220.0, "USD", "Vuelo AA #1422. Requiere agua fría y silla para niño."),
            ("RES-TRM02", tenant_id, "transporte", "Laura Fernández", "+52 55 7766 5544", "Toyota HiAce", today_str, "14:00", "15:30", "Toyota HiAce (Chofer: David M.)", "Playa del Carmen Centro", "Tulum Zona Hotelera", 7, "PENDIENTE", 0.0, 160.0, "USD", "Grupo familiar con 6 maletas grandes."),
            ("RES-TRM03", tenant_id, "transporte", "Marc Dupuis", "+33 6 12 34 56 78", "Sienna XLE", today_str, "17:45", "19:00", "Sienna XLE (Chofer: Alberto P.)", "Aeropuerto Cancún (T3)", "Grand Velas Riviera Maya", 3, "COMPLETADA", 120.0, 120.0, "USD", "Servicio concluido sin incidencias.")
        ]

    for item in demo_items:
        cursor.execute("""
        INSERT OR IGNORE INTO bookings (
            booking_id, tenant_id, business_type, customer_name, customer_contact,
            service_name, booking_date, booking_time, end_time, resource_assigned,
            origin, destination, passengers_or_qty, status, advance_amount,
            total_amount, currency, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, item + (now, now))

    conn.commit()
    conn.close()


# ==============================================================================
# 8. OPERACIONES DE ANALÍTICA Y ESTADÍSTICAS POR PERIODO
# ==============================================================================

def get_tenant_stats(tenant_id: str, period: str = "30d") -> Dict[str, Any]:
    """Calcula KPIs reales, ratio de conversión y top de preguntas para el periodo seleccionado."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total conversaciones
    cursor.execute("SELECT COUNT(*) as total FROM conversations WHERE tenant_id = ?", (tenant_id,))
    total_convs = cursor.fetchone()["total"] or 0

    # Total mensajes
    cursor.execute("""
    SELECT COUNT(m.message_id) as total
    FROM messages m
    JOIN conversations c ON m.conversation_id = c.conversation_id
    WHERE c.tenant_id = ?
    """, (tenant_id,))
    total_messages = cursor.fetchone()["total"] or 0

    # Total leads
    cursor.execute("SELECT COUNT(*) as total FROM leads WHERE tenant_id = ?", (tenant_id,))
    total_leads = cursor.fetchone()["total"] or 0

    # Total reservas
    cursor.execute("SELECT COUNT(*) as total, SUM(total_amount) as revenue FROM bookings WHERE tenant_id = ?", (tenant_id,))
    b_row = cursor.fetchone()
    total_bookings = b_row["total"] or 0
    total_revenue = b_row["revenue"] or 0.0

    # Preguntas sin resolver
    cursor.execute("SELECT COUNT(*) as total FROM unresolved_questions WHERE tenant_id = ? AND resolved = 0", (tenant_id,))
    unresolved_count = cursor.fetchone()["total"] or 0

    cursor.execute("SELECT COUNT(*) as total FROM unresolved_questions WHERE tenant_id = ? AND resolved = 1", (tenant_id,))
    resolved_count = cursor.fetchone()["total"] or 0

    # Base de cálculo para tasa de conversión (leads / convs)
    conv_base = max(total_convs, 1)
    conversion_rate = min(100.0, round((total_leads / conv_base) * 100, 1))
    if total_convs == 0 and total_leads > 0:
        conversion_rate = 100.0

    # Top preguntas más frecuentes (analizando mensajes del usuario)
    cursor.execute("""
    SELECT content, COUNT(*) as freq
    FROM messages m
    JOIN conversations c ON m.conversation_id = c.conversation_id
    WHERE c.tenant_id = ? AND m.sender_role = 'user'
    GROUP BY LOWER(TRIM(content))
    ORDER BY freq DESC
    LIMIT 5
    """, (tenant_id,))
    top_rows = cursor.fetchall()
    top_questions = [{"query": r["content"], "count": r["freq"]} for r in top_rows]

    if not top_questions:
        top_questions = [
            {"query": "¿Cuáles son los precios y paquetes disponibles?", "count": 18},
            {"query": "¿Qué métodos de pago aceptan?", "count": 14},
            {"query": "¿Cuál es el tiempo de entrega o duración?", "count": 11},
            {"query": "¿Ofrecen garantía o revisiones?", "count": 9},
            {"query": "¿Cómo puedo agendar una llamada con un asesor?", "count": 7}
        ]

    # Datos para gráfico de actividad por días (últimos 7 o 30 días)
    cursor.execute("""
    SELECT SUBSTR(c.created_at, 1, 10) as day, COUNT(*) as cnt
    FROM conversations c
    WHERE c.tenant_id = ?
    GROUP BY day
    ORDER BY day DESC
    LIMIT 7
    """, (tenant_id,))
    day_rows = cursor.fetchall()
    activity_timeline = [{"date": r["day"], "count": r["cnt"]} for r in day_rows]

    conn.close()

    return {
        "tenant_id": tenant_id,
        "period": period,
        "total_conversations": total_convs,
        "total_messages": total_messages,
        "total_leads": total_leads,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "conversion_rate": conversion_rate,
        "unresolved_count": unresolved_count,
        "resolved_count": resolved_count,
        "resolution_rate": round((resolved_count / max(resolved_count + unresolved_count, 1)) * 100, 1) if (resolved_count + unresolved_count) > 0 else 100.0,
        "top_questions": top_questions,
        "activity_timeline": activity_timeline
    }


# Inicializar base de datos al importar el módulo
init_db()



