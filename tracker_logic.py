# tracker_logic.py (Nel progetto Streamlit originale)
import uuid
import time
import requests
import streamlit as st
from urllib.parse import quote_plus  # Importa per codificare l'URL

FLASK_TRACKER_BASE_URL = "http://127.0.0.1:5000"


def generate_tracking_pixel(recipient_email, company_name):
    """
    Genera un URL di tracking pixel unico e registra l'email con il server Flask.
    """
    tracking_id = str(uuid.uuid4())
    sent_at_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    email_registration_data = {
        "tracking_id": tracking_id,
        "email_id": tracking_id,
        "recipient_email": recipient_email,
        "company_name": company_name,
        "sent_at": sent_at_timestamp
    }

    try:
        response = requests.post(f"{FLASK_TRACKER_BASE_URL}/register_email", json=email_registration_data, timeout=5)
        response.raise_for_status()
        print(f"Successfully registered email with tracker server: {response.json()}")
    except requests.exceptions.RequestException as e:
        st.error(
            f"Errore nel registrare l'email con il server di tracciamento: {e}. Assicurati che il server sia attivo e l'URL sia corretto.")
        print(f"Error registering email with tracker server: {e}")
        return None

    # Il pixel URL punterà sempre al server Flask
    pixel_url = f"{FLASK_TRACKER_BASE_URL}/pixel/{tracking_id}.gif"

    # Ritorna sia l'ID di tracciamento che l'URL del pixel, e ora anche una funzione per generare link tracciati
    return tracking_id, pixel_url


def generate_tracked_link(tracking_id, original_url):
    """
    Genera un URL che passa attraverso il server di tracciamento Flask prima di reindirizzare.
    """
    # Codifica l'URL originale per poterlo passare come parte del percorso URL
    encoded_url = quote_plus(original_url)
    return f"{FLASK_TRACKER_BASE_URL}/click/{tracking_id}/{encoded_url}"


def get_tracking_status():
    """
    Recupera lo stato del tracciamento facendo una richiesta HTTP al server Flask.
    """
    try:
        print(f"Tentativo di recuperare lo stato da: {FLASK_TRACKER_BASE_URL}/status")
        response = requests.get(f"{FLASK_TRACKER_BASE_URL}/status", timeout=5)
        response.raise_for_status()
        print(f"Risposta ricevuta: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Errore nel recuperare lo stato di tracciamento dal server: {e}. "
                 f"Verifica che il server Flask sia in esecuzione all'indirizzo '{FLASK_TRACKER_BASE_URL}'.")
        print(f"Error fetching tracking status from server: {e}")
        return {}