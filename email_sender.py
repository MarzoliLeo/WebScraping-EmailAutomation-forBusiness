# email_sender.py
import json
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
from gemini_api import call_gemini_flash
# Importa generate_tracking_logic (che era generate_tracking_pixel in precedenza)
# e generate_tracked_link.
from tracker_logic import generate_tracking_logic, generate_tracked_link


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
                 f"L'email deve essere conforme al GDPR, non deve contenere informazioni sensibili, e deve essere adatta per un primo contatto, non fornire mai un template, ma una email come se fosse già compilata da parte dell'utente e non usare parentesi, per convincere il cliente puoi anche citare di soldi a fondo perduto per supportare l'attività di collaborazione." \
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

            # Usiamo generate_tracking_logic (ex generate_tracking_pixel) solo per ottenere il tracking_id
            tracking_result = generate_tracking_logic(to, company_name)

            tracking_id = None
            if tracking_result is None:
                print("Attenzione: Impossibile generare il tracking ID. L'email non sarà tracciata.")
            else:
                tracking_id, _ = tracking_result  # Catturiamo solo il tracking_id, ignoriamo pixel_url

            tracked_website_link_html = ""
            if tracking_id:
                original_website_url = "https://www.metaphoralab.it/"
                tracked_url = generate_tracked_link(tracking_id, original_website_url)
                # Modificato per non aggiungere un <br> extra, la formattazione del corpo HTML lo gestirà
                tracked_website_link_html = f'<p>Visita il nostro sito: <a href="{tracked_url}" target="_blank">MetaphoraLab</a></p>'

            # --- Modifiche qui per migliorare la formattazione HTML del message_text ---
            # Sostituisci le nuove righe singole con <br> per interruzioni di riga
            # Sostituisci doppie nuove righe (o più) con </p><p> per creare nuovi paragrafi
            # Questo è un approccio comune per convertire testo semplice con paragrafi in HTML.
            formatted_message_html = message_text.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n", "<br>")
            # Assicurati che l'intero blocco sia avvolto in <p> per iniziare correttamente
            formatted_message_html = f"<p>{formatted_message_html}</p>"

            # Prepara la versione HTML del messaggio completo
            html_message = f"""
            <html>
                <body>
                    {formatted_message_html} 
                    {tracked_website_link_html}
                </body>
            </html>
            """
            # Prepara la versione di testo semplice del messaggio
            plain_message = message_text

            # È importante che la versione plain sia MIMEText('plain') e la versione HTML sia MIMEText('html')
            # C'era un errore qui nel codice fornito: entrambe erano 'html'.
            msg.attach(MIMEText(plain_message, "plain", "utf-8"))  # Testo semplice
            msg.attach(MIMEText(html_message, "html", "utf-8"))    # Versione HTML

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

            return True, f"Inviata (ID: {result['id']})"
        except Exception as e:
            return False, f"Errore: {str(e)}"