# email_sender.py
import json
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
from gemini_api import call_gemini_flash
# Importa solo generate_tracking_pixel, ma lo useremo per ottenere il tracking_id
# Poi useremo generate_tracked_link per il link.
from tracker_logic import generate_tracking_pixel, generate_tracked_link  # Importa anche questa


class EmailSender:
    def __init__(self):
        pass

    def extract_all_emails(self, df):
        all_emails = []
        for entry in df["Email trovate"]:
            if isinstance(entry, str):
                all_emails += [e.strip() for e in entry.split(",") if e.strip()]
        return list(set(all_emails))

    def generate_bulk_message(self, name_of_the_business, example_site):
        prompt = f"Scrivi un'email breve, formale e professionale per proporre una collaborazione lavorativa con un azienda che si occupa di {name_of_the_business}. " \
                 f"Cita il fatto che hai visitato il loro sito {example_site}  e che hai trovato il loro lavoro molto interessante." \
                 f"Inserisci sempre nella mail una proposta per poter visitare il nostro sitoweb https://www.metaphoralab.it/" \
                 f"L'email deve essere conforme al GDPR, non deve contenere informazioni sensibili, e deve essere adatta per un primo contatto, non inserire alcun tipo di campo da compilare da parte dell'utente e non usare parentesi, per convincere il cliente puoi anche citare di soldi a fondo perduto per supportare l'attività di collaborazione." \
                 f"Firma sempre come Metaphora." \
                 f"Non includere mai l'oggetto nella mail." \
                 f"Scrivi in italiano."
        system_instruction = "Sei un esperto di comunicazione aziendale. Il tuo compito è scrivere solo il testo dell'email, senza introduzioni o spiegazioni."
        return call_gemini_flash(prompt, system_instruction, temperature=0.8, max_tokens=500)

    def send_email(self, to, subject, message_text, company_name):
        try:
            creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.send"])
            service = build("gmail", "v1", credentials=creds)

            msg = MIMEMultipart("alternative")
            msg["to"] = to
            msg["subject"] = subject

            # Usiamo generate_tracking_pixel solo per ottenere il tracking_id
            # Non useremo l'html_pixel_part generato qui.
            tracking_result = generate_tracking_pixel(to, company_name)

            tracking_id = None
            if tracking_result is None:
                print("Attenzione: Impossibile generare il tracking ID. L'email non sarà tracciata.")
            else:
                tracking_id, _ = tracking_result  # Catturiamo solo il tracking_id, ignoriamo pixel_url

            # --- Nuova parte per il link tracciato a MetaphoraLab ---
            tracked_website_link_html = ""
            if tracking_id:  # Genera il link tracciato solo se abbiamo un tracking_id valido
                original_website_url = "https://www.metaphoralab.it/"
                # Genera l'URL tracciato utilizzando il tracking_id
                tracked_url = generate_tracked_link(tracking_id, original_website_url)
                # Inserisci il link tracciato nel corpo HTML. Aggiunto <br> per nuova riga.
                tracked_website_link_html = f'<br><p>Visita il nostro sito: <a href="{tracked_url}" target="_blank">MetaphoraLab</a></p>'
            # --- Fine nuova parte ---

            # Prepara la versione HTML del messaggio
            # Lascia message_text come testo semplice e aggiungi solo il link tracciato nell'HTML
            html_message = f"""
            <html>
                <body>
                    {tracked_website_link_html}
                </body>
            </html>
            """
            # Prepara la versione di testo semplice del messaggio
            # Questa parte conterrà il message_text completo con le sue \n
            plain_message = message_text

            msg.attach(MIMEText(plain_message, "plain", "utf-8"))  # Il testo normale
            msg.attach(MIMEText(html_message, "html", "utf-8"))  # La parte HTML con il link

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

            return True, f"Inviata (ID: {result['id']})"
        except Exception as e:
            return False, f"Errore: {str(e)}"