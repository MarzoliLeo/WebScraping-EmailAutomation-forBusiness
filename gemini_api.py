# gemini_api.py
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

client = genai.Client(api_key="AIzaSyBzY3R-z4s5VgEiTURI11od-b-DpWaAdYM")  # <-- Proteggi questa chiave in produzione

def call_gemini_flash(prompt, system_instruction, temperature=0.7, max_tokens=800):
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens
        )
    )
    logging.debug(f"📥 Risposta grezza da Gemini: {response.text}")
    return response.text.strip()
