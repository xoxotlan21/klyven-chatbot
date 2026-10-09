"""
Servicio de Transcripción de Notas de Voz y Audio (WhatsApp / Web).
Utiliza Google Gemini Multimodal REST API para convertir voz a texto con detección de intención.
"""

import os
import base64
from typing import Any, Dict
import requests


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/mp3", api_key: str = "") -> Dict[str, Any]:
    """
    Transcribe una nota de voz usando la API de Gemini enviando el audio en base64.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return {
            "success": False,
            "error": "Falta la clave API de Gemini.",
            "transcription": ""
        }

    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_audio
                        }
                    },
                    {
                        "text": (
                            "Transcribe exactamente el mensaje hablado en este audio. "
                            "Devuelve ÚNICAMENTE el texto literal transcrito, sin comentarios adicionales ni introducciones."
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1
        }
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                if parts:
                    transcription = parts[0].get("text", "").strip()
                    return {
                        "success": True,
                        "transcription": transcription,
                        "error": None
                    }
        return {
            "success": False,
            "error": f"Error de transcripción HTTP {r.status_code}: {r.text[:120]}",
            "transcription": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Fallo al procesar audio: {str(e)}",
            "transcription": ""
        }

