# tracker_logic.py
import uuid
import time
import requests # Importa requests
import streamlit as st
from urllib.parse import quote_plus
# Rimuovi l'import di google.oauth2.credentials e build
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
import base64
import re
from datetime import datetime, timedelta, timezone

# Usa l'URL del server Flask deployato
FLASK_TRACKER_BASE_URL = "https://marzoli95.pythonanywhere.com"

# Rimuovi l'import di get_gmail_service da qui
# from gmail_config import get_gmail_service

def generate_tracking_logic(recipient_email, company_name):
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

    pixel_url = f"{FLASK_TRACKER_BASE_URL}/pixel/{tracking_id}.gif"
    return tracking_id, pixel_url


def generate_tracked_link(tracking_id, original_url):
    """
    Genera un URL che passa attraverso il server di tracciamento Flask prima di reindirizzare.
    """
    encoded_url = quote_plus(original_url)
    return f"{FLASK_TRACKER_BASE_URL}/click/{tracking_id}/{encoded_url}"


def get_tracking_status():
    """
    Recupera lo stato del tracciamento facendo una richiesta HTTP al server Flask.
    """
    try:
        response = requests.get(f"{FLASK_TRACKER_BASE_URL}/status", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Errore nel recuperare lo stato di tracciamento dal server: {e}. "
                 f"Verifica che il server Flask sia in esecuzione all'indirizzo '{FLASK_TRACKER_BASE_URL}'.")
        print(f"Error fetching tracking status from server: {e}")
        return {}


# La funzione check_for_replies_and_bounces DEVE essere sul server Flask
# perché richiede l'accesso diretto a Gmail API tramite l'account dell'utente.
# Spostiamo questa logica da Streamlit (tracker_logic.py) al server Flask (app.py).

# Rimuovi check_for_replies_and_bounces da qui!
# Non può essere eseguita direttamente da Streamlit Cloud perché non ha accesso
# ai token OAuth degli utenti per leggere le loro caselle di posta.
# Il server Flask è il luogo appropriato per questa logica.
# Quindi, DEVI SPOSARE TUTTO IL CONTENUTO DELLA FUNZIONE `check_for_replies_and_bounces`
# nel tuo `app.py` del server Flask, magari in un endpoint chiamato `/check_gmail_status`.
# A quel punto, Streamlit chiamerà quell'endpoint sul server Flask.

# PER ORA, LASCIO LO STUB QUI PER EVITARE ERRORI DI IMPORTAZIONE,
# MA SAPPI CHE DEVE ESSERE IMPLEMENTATA SUL SERVER FLASK.
def check_for_replies_and_bounces():
    """
    Questa funzione DEVE essere implementata sul server Flask,
    non può essere eseguita direttamente da Streamlit Cloud.
    """
    print("ATTENZIONE: check_for_replies_and_bounces dovrebbe essere eseguita sul server Flask.")
    # Potresti implementare una chiamata HTTP a un endpoint sul server Flask qui
    # se vuoi che Streamlit la attivi.

    # Esempio di come Streamlit potrebbe chiedere al Flask server di controllare le email:
    # try:
    #     user_email = st.session_state.get("authenticated_user_email")
    #     if user_email:
    #         response = requests.post(f"{FLASK_TRACKER_BASE_URL}/check_gmail_status_for_user", json={"user_email": user_email})
    #         response.raise_for_status()
    #         print("Server Flask ha controllato le email per risposte/rimbalzi.")
    #     else:
    #         print("Nessun utente autenticato per controllare le risposte/rimbalzi.")
    # except requests.exceptions.RequestException as e:
    #     st.error(f"Errore nel richiedere il controllo email al server Flask: {e}")

    # In questo momento, la tua logica di check_for_replies_and_bounces nel file app.py del server
    # dovrà essere eseguita periodicamente lì (es. con un cron job su PythonAnywhere, o come parte del tuo script Flask).
    pass

# Rimuovi _get_email_part_data da qui, poiché è una funzione di supporto per check_for_replies_and_bounces
# e quest'ultima ora risiede sul server Flask.