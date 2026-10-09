"""
Servicio de Importación y Exportación de Tarifas en Excel / CSV.
Permite a cualquier dueño de negocio subir su lista de precios en Excel sin tocar código JSON.
"""

import io
import csv
import json
from typing import Any, Dict, List, Tuple


def generate_sample_pricing_csv() -> str:
    """Genera una plantilla CSV de ejemplo con encabezados y 4 filas representativas."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "origen_zona",
        "destino_zona",
        "id_sku",
        "precio_sencillo",
        "precio_redondo",
        "aplica_parada_extra"
    ])
    writer.writerow(["Aeropuerto Cancún (CUN)", "Zona Hotelera Cancún", "VAN-SUB-01", 45.0, 80.0, 15.0])
    writer.writerow(["Aeropuerto Cancún (CUN)", "Playa del Carmen", "VAN-SUB-01", 75.0, 140.0, 20.0])
    writer.writerow(["Aeropuerto Cancún (CUN)", "Akumal", "VAN-SUB-01", 115.0, 210.0, 25.0])
    writer.writerow(["Aeropuerto Cancún (CUN)", "Tulum", "VAN-SUB-01", 135.0, 250.0, 25.0])
    return output.getvalue()


def parse_pricing_csv(csv_content: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Lee y valida un archivo CSV de tarifas subido por el negocio.
    Devuelve (éxito, mensaje, lista_de_precios_json).
    """
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        required_cols = {"origen_zona", "destino_zona", "id_sku", "precio_sencillo"}
        
        # Normalizar encabezados (quitar espacios, minúsculas)
        fieldnames = {f.strip().lower(): f for f in (reader.fieldnames or [])}
        if not required_cols.issubset(fieldnames.keys()):
            missing = required_cols - set(fieldnames.keys())
            return False, f"Faltan columnas obligatorias en el archivo: {', '.join(missing)}", []

        pricing_list = []
        for idx, row in enumerate(reader, start=1):
            # Limpiar fila
            row_clean = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            origen = row_clean.get("origen_zona")
            destino = row_clean.get("destino_zona")
            sku = row_clean.get("id_sku")
            
            if not origen or not destino or not sku:
                continue

            try:
                precio_sencillo = float(row_clean.get("precio_sencillo", 0))
            except ValueError:
                return False, f"Error en fila {idx}: El precio sencillo debe ser un número válido.", []

            precio_redondo = None
            if row_clean.get("precio_redondo"):
                try:
                    precio_redondo = float(row_clean["precio_redondo"])
                except ValueError:
                    precio_redondo = precio_sencillo * 1.85  # Estimado si viene mal

            parada_extra = 0.0
            if row_clean.get("aplica_parada_extra"):
                try:
                    parada_extra = float(row_clean["aplica_parada_extra"])
                except ValueError:
                    parada_extra = 0.0

            pricing_list.append({
                "id_precio": f"PRC-{idx:03d}",
                "id_sku": sku,
                "origen_zona": origen,
                "destino_zona": destino,
                "precio_sencillo": precio_sencillo,
                "precio_redondo": precio_redondo,
                "aplica_parada_extra": parada_extra
            })

        if not pricing_list:
            return False, "El archivo CSV no contiene filas de tarifas válidas.", []

        return True, f"Se importaron exitosamente {len(pricing_list)} tarifas oficiales.", pricing_list

    except Exception as e:
        return False, f"Error al procesar el archivo CSV: {str(e)}", []


def pricing_json_to_csv(pricing_json_str: str) -> str:
    """Convierte la matriz JSON actual en un archivo CSV descargable."""
    try:
        data = json.loads(pricing_json_str)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["origen_zona", "destino_zona", "id_sku", "precio_sencillo", "precio_redondo", "aplica_parada_extra"])
        for item in data:
            writer.writerow([
                item.get("origen_zona", ""),
                item.get("destino_zona", ""),
                item.get("id_sku", ""),
                item.get("precio_sencillo", 0.0),
                item.get("precio_redondo", ""),
                item.get("aplica_parada_extra", 0.0)
            ])
        return output.getvalue()
    except Exception:
        return generate_sample_pricing_csv()

