# email_sender.py

import smtplib
from email.message import EmailMessage
import pandas as pd
from llama_cpp import Llama  # importa il modello localmente

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

    def generate_bulk_message(self, example_site):
        if self.llm is None:
            self.llm = get_llm()  # lazy import interno

        prompt = (
            f"Scrivi una breve email professionale in italiano da parte di un'azienda tecnologica che vuole offrire una collaborazione. "
            f"Il tono deve essere amichevole e formale. Includi un oggetto e firma come Metaphora, non specificare nomi reali. "
            f"Il messaggio deve essere adatto a un primo contatto e con l'obiettivo di fissare una prima call di conoscenza per parlare meglio dei propri servizi. "
            f"Sapendo che l'azienda si occupa di soluzioni immersive digitali: VR, AR, AI, Metaverso, Creazione di modelli 3D custom. "
            f"Inserisci come esempio il sito {example_site}."
        )
        output = self.llm(prompt=f"[INST] {prompt} [/INST]", max_tokens=300, temperature=0.7)
        return output["choices"][0]["text"].strip()

    def send_email(self, to_address, subject, body, sender_email, sender_password):
        try:
            msg = EmailMessage()
            msg["From"] = sender_email
            msg["To"] = to_address
            msg["Subject"] = subject
            msg.set_content(body)

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(sender_email, sender_password)
                smtp.send_message(msg)
            return True, "Inviata con successo"
        except Exception as e:
            return False, str(e)

    def extract_all_emails(self, df):
        emails = set()
        for _, row in df.iterrows():
            for email in row["Email trovate"].split(","):
                emails.add(email.strip())
        return list(emails)
