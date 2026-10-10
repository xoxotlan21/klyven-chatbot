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
        cursor.execute("""
        UPDATE tenants
        SET business_name = ?, industry = ?, currency = ?, support_phone = ?, config_json = ?
        WHERE tenant_id = ?
        """, (business_name, industry, currency, support_phone, config_json, tenant_id))
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


# Inicializar base de datos al importar el módulo
init_db()


