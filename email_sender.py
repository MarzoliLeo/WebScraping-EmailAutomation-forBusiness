# email_sender.py
import json
import base64
import uuid
import re
import requests # Importa requests

# Modifica per puntare all'URL del server Flask su PythonAnywhere
FLASK_SERVER_BASE_URL = "https://marzoli95.pythonanywhere.com"

from gemini_api import call_gemini_flash # Assicurati che gemini_api esista o usa utils_llm
from tracker_logic import generate_tracking_logic, generate_tracked_link

# Rimuovi l'import di get_gmail_service e la dipendenza diretta da Gmail API qui
# from gmail_config import get_gmail_service

class EmailSender:
    def __init__(self):
        # self.gmail_service = get_gmail_service() # Rimuovi questa riga
        pass # Non abbiamo più un servizio Gmail diretto qui

    def extract_all_emails(self, df):
        all_emails = []
        for entry in df["Email trovate"]:
            if isinstance(entry, str):
                all_emails += [e.strip() for e in entry.split(",") if e.strip()]
        return list(set(all_emails))

    def generate_bulk_message(self, name_of_the_business, example_site):
        # La logica Gemini rimane invariata, ma assicurati che call_gemini_flash sia importato correttamente
        # (nel tuo contesto, sembra essere in utils_llm.py, quindi potresti dover importare da lì)
        prompt = f"Scrivi un'email breve, formale e professionale per proporre una collaborazione lavorativa con un azienda che si occupa di {name_of_the_business}. " \
                 f"Cita il fatto che hai visitato il loro sito {example_site}  e che hai trovato il loro lavoro molto interessante." \
                 f"Inserisci sempre nella mail una proposta per poter visitare il nostro sitoweb https://www.metaphoralab.it/ . " \
                 f"Non inserire mai parentesi e non chiedere mai all'utente di inserire elementi testuali per completare l'email." \
                 f"L'email deve essere conforme al GDPR, non deve contenere informazioni sensibili, e deve essere adatta per un primo contatto, per convincere il cliente puoi anche citare di soldi a fondo perduto per supportare l'attività di collaborazione." \
                 f"Firma sempre come Metaphora." \
                 f"Non includere mai l'oggetto nella mail." \
                 f"Scrivi in italiano."
        system_instruction = "Sei un esperto di comunicazione aziendale. Il tuo compito è scrivere solo il testo dell'email, senza introduzioni o spiegazioni."
        # Assicurati di chiamare il call_gemini_flash corretto (dal tuo utils_llm.py)
        return call_gemini_flash(prompt, system_instruction=system_instruction, temperature=0.8, max_tokens=500)


    def send_email(self, to, subject, message_text, company_name):
        # Questa funzione invia i dati al server Flask per l'invio effettivo
        # Non ha più bisogno di self.gmail_service qui.
        try:
            # Genera tracking_id e URL tracciati (questo può rimanere su Streamlit)
            tracking_result = generate_tracking_logic(to, company_name)
            tracking_id = None
            if tracking_result is None:
                print("Attenzione: Impossibile generare il tracking ID. L'email non sarà tracciata.")
                return False, "Errore nella generazione del tracking ID."
            else:
                tracking_id, _ = tracking_result # pixel_url non è più necessario qui, ma il tracking_id sì

            original_website_url = "https://www.metaphoralab.it/"

            # Prepara il corpo HTML completo con il tracking pixel e il link tracciato
            message_html_content = message_text.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n", "<br>")
            message_html_content = f"<p>{message_html_content}</p>"

            # Inserimento del tracking_id nel commento HTML
            # e sostituzione del link metaphora.it con quello tracciato
            url_pattern = re.compile(r'(https?://)?(www\.)?metaphoralab\.it/?', re.IGNORECASE)
            match = url_pattern.search(message_html_content)

            if match:
                tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                link_replacement = f'<a href="{tracked_full_url}" target="_blank">https://metaphora.it</a>'
                message_html_content = url_pattern.sub(link_replacement, message_html_content, 1)
            else:
                # Se il link metaphora.it non è nel testo, aggiungiamo un link tracciato separato
                tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                tracked_website_link_html = f'<p>Visita il nostro sito: <a href="{tracked_full_url}" target="_blank">https://metaphora.it</a></p>'
                message_html_content += tracked_website_link_html


            # Aggiungi il pixel invisibile per il tracciamento delle aperture
            # e il tracking_id come commento invisibile per il tracciamento delle risposte
            pixel_img_url = f"{FLASK_SERVER_BASE_URL}/pixel/{tracking_id}.gif"

            final_html_message = f"""
            <html>
                <body>
                    {message_html_content}
                    <img src="{pixel_img_url}" width="1" height="1" style="display:none;" />
                    <p style="display: none;">{tracking_id}</p> </body>
            </html>
            """

            # Assicurati che l'email dell'utente sia disponibile in session_state
            user_email = st.session_state.get("authenticated_user_email")
            if not user_email:
                return False, "Utente non autenticato. Si prega di effettuare il login con Gmail."

            # Invia la richiesta al server Flask
            payload = {
                "user_email": user_email,
                "to": to,
                "subject": subject,
                "message_html": final_html_message, # Invia l'HTML completo al server Flask
                "company_name": company_name,
                "tracking_id": tracking_id # Passa il tracking_id al server Flask
            }

            response = requests.post(f"{FLASK_SERVER_BASE_URL}/send_email_from_user", json=payload)
            response.raise_for_status() # Solleva un'eccezione per risposte HTTP non 2xx

            result = response.json()
            return True, f"Inviata (ID: {result.get('tracking_id', 'N/A')})" # Puoi usare l'ID del tracking o l'ID della mail

        except requests.exceptions.RequestException as req_e:
            error_msg = f"Errore di rete/server Flask: {req_e}"
            if req_e.response is not None:
                error_msg += f" - Risposta server: {req_e.response.text}"
            return False, error_msg
        except Exception as e:
            return False, f"Errore imprevisto durante l'invio: {str(e)}"