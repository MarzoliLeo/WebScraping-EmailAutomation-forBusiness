# email_sender.py

import base64
import os

import pandas as pd
from email.message import EmailMessage
from llama_cpp import Llama

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Lazy loader interno al file (senza usare utils)
_llm = None
def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(model_path="models/mistral-7b-instruct-v0.1.Q4_K_M.gguf", n_ctx=2048, n_threads=4)
    return _llm

class EmailSender:
    def __init__(self):
        self.llm = None
        self.service = self.authenticate_gmail()

    def authenticate_gmail(self):
        SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def generate_bulk_message(self, example_site):
        if self.llm is None:
            self.llm = get_llm()

        prompt = (
            f"Scrivi una email professionale in italiano sapendo che l'azienda si occupa di soluzioni immersive digitali: VR, AR, AI, Metaverso, Creazione di modelli 3D custom. "
            f"Il tono deve essere amichevole e formale. Includi un oggetto e firma come Metaphora, non specificare nomi reali e non inserire campi da compilare. "
            f"Il messaggio deve essere adatto a un primo contatto e con l'obiettivo di fissare una prima call di conoscenza per parlare meglio dei propri servizi."
            f"Crea una sezione all'interno della mail dove si espongono i servizi aziendali in breve e cita la possibilità di disporre di sussidi a fondo perduto per iniziare una collaborazione. "
            f"Inserisci come esempio il sito {example_site}."
        )
        output = self.llm(prompt=f"[INST] {prompt} [/INST]", max_tokens=300, temperature=0.7)
        return output["choices"][0]["text"].strip()

    def send_email(self, to_address, subject, body, sender_email=None, sender_password=None):
        try:
            message = EmailMessage()
            message.set_content(body)
            message['To'] = to_address
            message['From'] = "me"
            message['Subject'] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            send_result = self.service.users().messages().send(
                userId="me",
                body={"raw": encoded_message}
            ).execute()

            return True, f"Inviata con successo (ID: {send_result['id']})"
        except Exception as e:
            return False, str(e)

    def extract_all_emails(self, df):
        emails = set()
        for _, row in df.iterrows():
            for email in row["Email trovate"].split(","):
                emails.add(email.strip())
        return list(emails)
