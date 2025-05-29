# email_sender.py - Versione AGGIORNATA per tracciamento risposte (HTML invisibile)
import json
import base64
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
import re
from gemini_api import call_gemini_flash
from tracker_logic import generate_tracking_logic, generate_tracked_link
from gmail_config import get_gmail_service


class EmailSender:
    def __init__(self):
        self.gmail_service = get_gmail_service()

    def extract_all_emails(self, df):
        all_emails = []
        for entry in df["Email trovate"]:
            if isinstance(entry, str):
                all_emails += [e.strip() for e in entry.split(",") if e.strip()]
        return list(set(all_emails))

    def generate_bulk_message(self, name_of_the_business, example_site):
        prompt = f"Scrivi un'email breve, formale e professionale per proporre una collaborazione lavorativa con un azienda che si occupa di {name_of_the_business}. " \
                 f"Cita il fatto che hai visitato il loro sito {example_site}  e che hai trovato il loro lavoro molto interessante." \
                 f"Inserisci sempre nella mail una proposta per poter visitare il nostro sitoweb https://www.metaphoralab.it/ . " \
                 f"Non inserire mai parentesi e non chiedere mai all'utente di inserire elementi testuali per completare l'email." \
                 f"L'email deve essere conforme al GDPR, non deve contenere informazioni sensibili, e deve essere adatta per un primo contatto, per convincere il cliente puoi anche citare di soldi a fondo perduto per supportare l'attività di collaborazione." \
                 f"Firma sempre come Metaphora." \
                 f"Non includere mai l'oggetto nella mail." \
                 f"Scrivi in italiano."
        system_instruction = "Sei un esperto di comunicazione aziendale. Il tuo compito è scrivere solo il testo dell'email, senza introduzioni o spiegazioni."
        return call_gemini_flash(prompt, system_instruction, temperature=0.8, max_tokens=500)

    def send_email(self, to, subject, message_text, company_name):
        try:
            service = self.gmail_service

            msg = MIMEMultipart("alternative")
            msg["to"] = to
            msg["subject"] = subject

            tracking_result = generate_tracking_logic(to, company_name)

            tracking_id = None
            if tracking_result is None:
                print("Attenzione: Impossibile generare il tracking ID. L'email non sarà tracciata.")
            else:
                tracking_id, _ = tracking_result

            original_website_url = "https://www.metaphoralab.it/"
            tracked_url_html = ""

            if tracking_id:
                url_pattern = re.compile(r'(https?://)?(www\.)?metaphoralab\.it/?', re.IGNORECASE)
                match = url_pattern.search(message_text)

                if match:
                    tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                    link_replacement = f'<a href="{tracked_full_url}" target="_blank">https://metaphora.it</a>'
                    message_text_for_html = url_pattern.sub(link_replacement, message_text, 1)
                else:
                    tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                    tracked_website_link_html = f'<p>Visita il nostro sito: <a href="{tracked_full_url}" target="_blank">https://metaphora.it</a></p>'
                    message_text_for_html = message_text
            else:
                message_text_for_html = message_text

            formatted_message_html = message_text_for_html.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace(
                "\n", "<br>")
            formatted_message_html = f"<p>{formatted_message_html}</p>"

            final_html_content = formatted_message_html
            if tracking_id and not match and 'tracked_website_link_html' in locals() and tracked_website_link_html:
                final_html_content += tracked_website_link_html

            # *** CORREZIONE QUI: INSERIMENTO DEL TRACKING_ID COME COMMENTO HTML INVISIBILE ***
            # Questa parte è stata riordinata e corretta per assicurare che il tracking_id sia SEMPRE presente
            # nell'HTML, se generato.
            html_message_with_tracking = f"""
            <html>
                <body>
                    {final_html_content}
                    <p style="display: none;">{tracking_id}</p>
                    </body>
            </html>
            """

            # Allega sia la versione plain che quella HTML.
            # La versione HTML includerà il commento con il tracking_id.
            msg.attach(MIMEText(formatted_message_html, "plain", "utf-8"))
            msg.attach(MIMEText(html_message_with_tracking, "html", "utf-8"))

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

            return True, f"Inviata (ID: {result['id']})"
        except Exception as e:
            return False, f"Errore: {str(e)}"