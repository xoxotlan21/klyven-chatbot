"""
Servicio de CRM y Captura de Leads Calificados.
Almacena todos los prospectos que cotizan para seguimiento comercial y remarketing.
"""

import io
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3

from database import DB_FILE


def init_leads_table():
    """Crea la tabla de leads en SQLite si no existe."""
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        customer_name TEXT,
        customer_contact TEXT,
        service_requested TEXT,
        quoted_price REAL,
        currency TEXT,
        status TEXT DEFAULT 'NUEVO_PROSPECTO',
        notes TEXT,
        created_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()


def record_lead(
    tenant_id: str,
    service: str,
    price: float,
    currency: str,
    contact: Optional[str] = None,
    name: Optional[str] = None,
    notes: Optional[str] = None
) -> int:
    """Registra un nuevo lead en el CRM relacional."""
    init_leads_table()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO leads (tenant_id, customer_name, customer_contact, service_requested, quoted_price, currency, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (tenant_id, name or "Prospecto Web", contact or "En chat", service, price, currency, notes or "", now))
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def get_all_leads(tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene todos los prospectos capturados con opción de filtro por tenant."""
    init_leads_table()
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if tenant_id:
        cursor.execute("SELECT * FROM leads WHERE tenant_id = ? ORDER BY lead_id DESC", (tenant_id,))
    else:
        cursor.execute("SELECT * FROM leads ORDER BY lead_id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_leads_to_csv(tenant_id: Optional[str] = None) -> str:
    """Exporta los leads a formato CSV compatible con Excel, Google Sheets, HubSpot o Salesforce."""
    leads = get_all_leads(tenant_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tenant", "Cliente", "Contacto", "Servicio Solicitado", "Precio Cotizado", "Moneda", "Estado", "Fecha"])
    for l in leads:
        writer.writerow([
            l.get("lead_id"),
            l.get("tenant_id"),
            l.get("customer_name"),
            l.get("customer_contact"),
            l.get("service_requested"),
            l.get("quoted_price"),
            l.get("currency"),
            l.get("status"),
            l.get("created_at")
        ])
    return output.getvalue()

