# gemini_api.py
import logging
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv() #Looks for the .env file in the files of the project.

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

# Recupera la chiave API da una variabile d'ambiente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logging.error("La chiave API di Gemini non è stata trovata. Assicurati di averla impostata come variabile d'ambiente 'GEMINI_API_KEY'.")
    raise ValueError("GEMINI_API_KEY non impostata.")

client = genai.Client(api_key=GEMINI_API_KEY)

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
