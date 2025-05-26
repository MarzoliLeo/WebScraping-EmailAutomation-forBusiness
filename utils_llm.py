import os
import logging
from google import genai
from google.genai import types


# CONFIGURA LOGGING SU STDERR A LIVELLO DEBUG
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")  # :contentReference[oaicite:0]{index=0}

# Inizializzazione
client = genai.Client(api_key="AIzaSyBzY3R-z4s5VgEiTURI11od-b-DpWaAdYM") #Gemini API Key

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
