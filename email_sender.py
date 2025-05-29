# email_sender.py
import json
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
import re # Importa il modulo re per le espressioni regolari
from gemini_api import call_gemini_flash
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
            creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.send"])
            service = build("gmail", "v1", credentials=creds)

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
            tracked_url_html = "" # Inizializza a vuoto

            # --- LOGICA PER IL LINK TRACCIATO INTELLIGENTE ---
            # 1. Cerca l'URL originale nel message_text
            # Usiamo re.escape per gestire correttamente i caratteri speciali nell'URL se necessario
            # e re.IGNORECASE per una ricerca case-insensitive.
            # Il pattern cerca l'URL intero.
            if tracking_id:
                # Pattern per trovare l'URL sia con che senza 'http(s)://'
                # Questo pattern è più robusto se l'AI o l'utente scrive l'URL in modi leggermente diversi
                url_pattern = re.compile(r'(https?://)?(www\.)?metaphoralab\.it/?', re.IGNORECASE)

                # Cerca l'URL nel message_text
                match = url_pattern.search(message_text)

                if match:
                    # Se l'URL è trovato, sostituiscilo con il link tracciato nel formatted_message_html
                    # Non aggiungiamo tracked_website_link_html separatamente in questo caso
                    tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                    # Sostituisci l'URL originale nel testo con il link HTML tracciato
                    # Usiamo match.group(0) per ottenere la stringa esatta trovata dal pattern
                    # Non creiamo un <p> qui, perché formatted_message_html lo farà per noi.
                    link_replacement = f'<a href="{tracked_full_url}" target="_blank">https://metaphora.it</a>'
                    # Questo è il testo che verrà passato per la formattazione HTML.
                    # message_text_for_html si aggiorna con il link HTML.
                    message_text_for_html = url_pattern.sub(link_replacement, message_text, 1) # Sostituisci solo la prima occorrenza
                else:
                    # Se l'URL non è presente nel testo, aggiungilo in fondo come prima
                    # e imposta message_text_for_html al message_text originale.
                    tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                    tracked_website_link_html = f'<p>Visita il nostro sito: <a href="{tracked_full_url}" target="_blank">https://metaphora.it</a></p>'
                    message_text_for_html = message_text # Usa il testo originale per la formattazione
            else:
                # Se non c'è tracking_id, non c'è link tracciato, usa il testo originale
                message_text_for_html = message_text
            # --- FINE LOGICA LINK TRACCIATO INTELLIGENTE ---


            # Sostituisci le nuove righe singole con <br> per interruzioni di riga
            # Sostituisci doppie nuove righe (o più) con </p><p> per creare nuovi paragrafi
            # Applica la formattazione a message_text_for_html (che ora contiene il link HTML se trovato e sostituito)
            formatted_message_html = message_text_for_html.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n", "<br>")
            formatted_message_html = f"<p>{formatted_message_html}</p>" # Avvolgi tutto in un <p>

            # Prepara la versione HTML del messaggio completo
            # Aggiungi tracked_website_link_html solo se non è stato già inserito nel formatted_message_html
            final_html_content = formatted_message_html
            if not match and tracked_website_link_html: # Se non c'è stata una sostituzione e il link dovrebbe essere aggiunto
                final_html_content += tracked_website_link_html


            html_message = f"""
            <html>
                <body>
                    {final_html_content}
                </body>
            </html>
            """
            plain_message = message_text

            msg.attach(MIMEText(plain_message, "plain", "utf-8"))
            msg.attach(MIMEText(html_message, "html", "utf-8"))

            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

            return True, f"Inviata (ID: {result['id']})"
        except Exception as e:
            return False, f"Errore: {str(e)}"