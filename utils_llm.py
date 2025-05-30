import os
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv() #Looks for the .env file in the files of the project.

# CONFIGURA LOGGING SU STDERR A LIVELLO DEBUG
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")  # :contentReference[oaicite:0]{index=0}

# Recupera la chiave API da una variabile d'ambiente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not GEMINI_API_KEY:
    logging.error("La chiave API di Gemini non è stata trovata. Assicurati di averla impostata come variabile d'ambiente 'GEMINI_API_KEY'.")
    raise ValueError("GEMINI_API_KEY non impostata.")

client = genai.Client(api_key=GEMINI_API_KEY)



def call_gemini_flash(prompt):
    response = client.models.generate_content(
        model="gemini-2.0-flash", #gemini-2.5-flash-preview-05-20
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction= "Sei un esperto di marketing. Il tuo output è SOLO un elenco di aziende nel formato <Nome Azienda> - <Sito Web>, niente altro.",
            temperature=0.9,
            max_output_tokens=800
        )
    )
    # Logga la risposta grezza
    logging.debug(f"📥 Risposta grezza da Gemini: {response.text}")

    return response.text
