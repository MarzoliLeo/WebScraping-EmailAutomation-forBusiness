# gmail_config.py
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request  # Necessario per il refresh del token
from googleapiclient.discovery import build

# Se si modificano questi ambiti, eliminare il file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send'
]


def get_gmail_service():
    """
    Ottiene il servizio Gmail API v1.
    Gestisce l'autenticazione, il refresh del token e la creazione del servizio.
    """
    creds = None
    # Il file token.json memorizza i token di accesso e di refresh dell'utente
    # ed è creato automaticamente quando il flusso di autorizzazione è completato per la prima volta.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Se non ci sono credenziali valide disponibili, permetti all'utente di effettuare l'accesso.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Se le credenziali sono scadute ma c'è un refresh token, prova a rinfrescarle
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Errore durante il refresh del token: {e}")
                # Se il refresh fallisce, forza una nuova autorizzazione
                os.remove('token.json')  # Elimina il token non valido
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            # Altrimenti, avvia il flusso di autorizzazione completo
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Salva le credenziali per la prossima esecuzione
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Costruisci e restituisci il servizio Gmail
    service = build('gmail', 'v1', credentials=creds)
    return service