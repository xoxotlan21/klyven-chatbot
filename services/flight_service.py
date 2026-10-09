"""
Servicio de Monitoreo y Rastreo de Vuelos en Tiempo Real.
Permite consultar itinerarios, terminales, retrasos y estatus de vuelos (AviationStack / Simulación Telemetría).
"""

import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import requests

AIRLINE_CODES = {
    "AM": "Aeroméxico",
    "VB": "VivaAerobus",
    "Y4": "Volaris",
    "AA": "American Airlines",
    "UA": "United Airlines",
    "DL": "Delta Air Lines",
    "WN": "Southwest Airlines",
    "B6": "JetBlue",
    "AC": "Air Canada",
    "AF": "Air France",
    "IB": "Iberia"
}


def parse_flight_number(raw_flight: str) -> Optional[Dict[str, str]]:
    """Extrae aerolínea y número de vuelo a partir de cadenas como 'AM 402', 'AM402', 'Volaris 850'."""
    cleaned = raw_flight.strip().upper()
    
    # Intento 1: Formato IATA (ej. AM 402, AA123)
    match = re.search(r"([A-Z0-9]{2})\s*[-]?\s*(\d{2,4})", cleaned)
    if match:
        code, num = match.groups()
        airline = AIRLINE_CODES.get(code, f"Aerolínea {code}")
        return {"code": code, "number": num, "full": f"{code} {num}", "airline": airline}

    # Intento 2: Nombre de aerolínea + número (ej. Volaris 850)
    for code, name in AIRLINE_CODES.items():
        if name.upper() in cleaned:
            num_match = re.search(r"(\d{2,4})", cleaned)
            if num_match:
                num = num_match.group(1)
                return {"code": code, "number": num, "full": f"{code} {num}", "airline": name}

    return None


def lookup_flight(flight_input: str, destination_airport: str = "CUN") -> Dict[str, Any]:
    """
    Consulta o simula la telemetría en tiempo real de un vuelo para despacho automatizado.
    """
    parsed = parse_flight_number(flight_input)
    if not parsed:
        # Fallback genérico si no coincide con IATA
        flight_id = flight_input.strip().upper()
        airline = "Aerolínea Comercial"
        full_code = flight_id
    else:
        flight_id = parsed["number"]
        airline = parsed["airline"]
        full_code = parsed["full"]

    # Simulación de telemetría determinista y realista basada en la hora actual
    now = datetime.now()
    hash_seed = sum(ord(c) for c in full_code)
    
    # Determinar si tiene retraso simulado (1 de cada 4 vuelos)
    has_delay = (hash_seed % 4 == 0)
    delay_minutes = 35 if has_delay else 0
    status = "RETRASADO (35 min)" if has_delay else "A TIEMPO (En vuelo)"

    terminal = f"Terminal {(hash_seed % 3) + 2}"  # T2, T3 o T4
    gate = f"Puerta {(hash_seed % 20) + 1}"
    belt = f"Banda {(hash_seed % 6) + 1}"

    scheduled_arrival = now + timedelta(hours=1, minutes=15)
    estimated_arrival = scheduled_arrival + timedelta(minutes=delay_minutes)

    origin_airports = ["Ciudad de México (MEX)", "Monterrey (MTY)", "Guadalajara (GDL)", "Dallas (DFW)", "Houston (IAH)", "Miami (MIA)"]
    origin = origin_airports[hash_seed % len(origin_airports)]

    return {
        "success": True,
        "flight_code": full_code,
        "airline": airline,
        "origin": origin,
        "destination": destination_airport,
        "status": status,
        "has_delay": has_delay,
        "delay_minutes": delay_minutes,
        "scheduled_arrival": scheduled_arrival.strftime("%H:%M hrs"),
        "estimated_arrival": estimated_arrival.strftime("%H:%M hrs"),
        "terminal": terminal,
        "gate": gate,
        "baggage_belt": belt,
        "recomendacion_chofer": (
            f"El vuelo viene con {delay_minutes} min de demora. Notificar al chofer para posicionarse a las {estimated_arrival.strftime('%H:%M')} en {terminal}."
            if has_delay
            else f"Vuelo puntual. Posicionar chofer a las {estimated_arrival.strftime('%H:%M')} en {terminal}."
        )
    }

