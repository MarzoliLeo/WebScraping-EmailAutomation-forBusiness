# email_sender.py
import json
from utils import get_llm
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText

class EmailSender:
    def __init__(self):
        self.llm = get_llm()

    def extract_all_emails(self, df):
        all_emails = []
        for entry in df["Email trovate"]:
            if isinstance(entry, str):
                all_emails += [e.strip() for e in entry.split(",") if e.strip()]
        return list(set(all_emails))

    def generate_bulk_message(self, example_site):
        prompt = f"[INST] Scrivi un'email breve, formale e professionale per proporre una collaborazione con un'azienda che si occupa di {example_site}. Non deve contenere informazioni sensibili, deve essere conforme al GDPR. [/INST]"
        output = self.llm(prompt=prompt, max_tokens=300, temperature=0.8, stop=["</s>"])
        return output["choices"][0]["text"].strip()

    def send_email(self, to, subject, message_text):
        try:
            creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.send"])
            service = build("gmail", "v1", credentials=creds)

            message = MIMEText(message_text, "plain", "utf-8")
            message["to"] = to
            message["subject"] = subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
            return True, f"Inviata (ID: {result['id']})"
        except Exception as e:
            return False, f"Errore: {str(e)}"
