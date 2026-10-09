# TravelSales.ai - Plataforma SaaS Multi-Tenant de Comercio Conversacional

Aplicación completa en Python de Inteligencia Comercial y Despacho Automatizado para agencias de transporte, tours y traslados privados, impulsada por **Google Gemini** y **Streamlit**.

---

## 🚀 Arquitectura y Archivos del Proyecto

```text
├── app.py                # Interfaz web interactiva con Streamlit (Chat + Panel Multi-Tenant)
├── engine.py             # Motor LLM (Google Gemini), inyección de contexto y parsing de JSON
├── system_prompt.md      # Prompt del sistema determinista (Reglas cardinales, FSM y esquema)
├── requirements.txt      # Dependencias del proyecto
└── README.md             # Guía de instalación y ejecución
```

---

## 🛠️ Instalación y Requisitos Previos

### 1. Clonar o situarse en el directorio del proyecto
Abre tu terminal en la carpeta del proyecto:
```bash
cd "/Users/andrew./Documents/Visual Studio Code/bot"
```

### 2. Crear y activar un entorno virtual (Recomendado)
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar las dependencias
```bash
pip install -r requirements.txt
```
*(Si no tienes el comando `pip` directo, puedes usar `python3 -m pip install -r requirements.txt`)*

---

## ⚡ Ejecución de la Aplicación

Para lanzar la interfaz web interactiva en tu navegador:
```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador predeterminado (usualmente en `http://localhost:8501`).

---

## 🔑 Configuración de la API Key de Google Gemini

1. Obtén una clave de API gratuita en [Google AI Studio](https://aistudio.google.com/).
2. Puedes proporcionarla de dos maneras:
   * **En la interfaz gráfica:** Ingrésala directamente en el campo **"🔑 Gemini API Key"** ubicado en la barra lateral izquierda.
   * **Como variable de entorno:**
     ```bash
     export GEMINI_API_KEY="tu_clave_api_aqui"
     streamlit run app.py
     ```

---

## 🏢 Características Multi-Tenant y Telemetría

* **Conmutador de Tenant en Caliente:** Cambia en tiempo real entre:
  * *Traslados Riviera Maya* (CUN / Akumal / Tulum / Playa del Carmen - Moneda USD)
  * *Los Cabos Luxury Expeditions* (SJD / Cabo San Lucas / Todos Santos - Moneda USD)
  * *CDMX VIP Executive Transfers* (AICM / Reforma / Santa Fe / Toluca - Moneda MXN)
* **Editores JSON en Vivo:** Modifica el catálogo de flota (`CATALOG_JSON`) y la matriz de precios (`PRICING_JSON`) directamente desde la barra lateral con validación sintáctica inmediata.
* **Máquina de Estados Finitos (FSM):** Visualización en tiempo real del estado de cada turno (`ESTADO_0` a `ESTADO_4`).
* **Integración de Checkout (Stripe Connect):** Genera dinámicamente enlaces y tarjetas de pago seguro cuando el cliente confirma la cotización.
* **Cero Alucinación:** Si un cliente consulta una ruta no listada en la matriz, el sistema activa la acción `AVISAR_OPERADOR_HUMANO` y transfiere al número de despacho correspondiente.

