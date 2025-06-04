# email_sender.py
import re
import requests  
from gemini_api import call_gemini_flash
from tracker_logic import generate_tracking_logic, generate_tracked_link  # tracker_logic also needs update

# Define your Flask server base URL
FLASK_SERVER_BASE_URL = "https://marzoli95.pythonanywhere.com"


class EmailSender:
    def __init__(self, user_email):
        # The user_email is now passed during initialization
        self.user_email = user_email
        # self.gmail_service = get_gmail_service() # REMOVE THIS LINE

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
        if not self.user_email:
            return False, "Errore: Nessun utente Gmail autenticato. Si prega di effettuare il login."

        try:
            tracking_result = generate_tracking_logic(to, company_name)

            tracking_id = None
            if tracking_result is None:
                print("Attenzione: Impossibile generare il tracking ID. L'email non sarà tracciata.")
            else:
                tracking_id, _ = tracking_result  # Pixel URL is not used here, only tracking_id

            original_website_url = "https://www.metaphoralab.it/"
            message_text_for_html = message_text
            final_html_content = ""

            if tracking_id:
                url_pattern = re.compile(r'(https?://)?(www\.)?metaphoralab\.it/?', re.IGNORECASE)
                match = url_pattern.search(message_text)

                if match:
                    tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                    # Replace the first occurrence of the URL in the message text with the tracked link
                    # This replaces the original link with the tracked link HTML.
                    link_replacement = f'<a href="{tracked_full_url}" target="_blank">https://metaphora.it</a>'
                    # Use a regex to find and replace the full URL string, ensuring 'https://' prefix if missing
                    # This is crucial for correctly tracking clicks.
                    message_text_for_html = url_pattern.sub(link_replacement, message_text, 1)
                    final_html_content = message_text_for_html.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace(
                        "\n", "<br>")
                    final_html_content = f"<p>{final_html_content}</p>"
                else:
                    # If the URL is not found in the original message text, append it as a tracked link
                    tracked_full_url = generate_tracked_link(tracking_id, original_website_url)
                    tracked_website_link_html = f'<p>Visita il nostro sito: <a href="{tracked_full_url}" target="_blank">https://metaphora.it</a></p>'
                    formatted_message_html = message_text.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n",
                                                                                                                   "<br>")
                    formatted_message_html = f"<p>{formatted_message_html}</p>"
                    final_html_content = formatted_message_html + tracked_website_link_html
            else:
                formatted_message_html = message_text.replace("\r\n", "\n").replace("\n\n", "</p><p>").replace("\n",
                                                                                                               "<br>")
                final_html_content = f"<p>{formatted_message_html}</p>"

            # Inject the tracking ID as an invisible HTML comment for reply tracking
            # This is key for the Flask server to identify replies
            html_message_with_tracking = f"""
            <html>
                <body>
                    {final_html_content}
                    <p style="display: none;">{tracking_id}</p>
                </body>
            </html>
            """
            # Prepare data for the Flask server
            payload = {
                "user_email": self.user_email,
                "to": to,
                "subject": subject,
                "message_html": html_message_with_tracking,  # Send the full HTML message
                "company_name": company_name,
                "tracking_id": tracking_id
            }

            # Send the email via your Flask server
            response = requests.post(f"{FLASK_SERVER_BASE_URL}/send_email_from_user", json=payload, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

            server_response = response.json()
            return True, f"Inviata (ID: {server_response.get('tracking_id', 'N/A')})"
        except requests.exceptions.RequestException as e:
            return False, f"Errore di comunicazione con il server di invio email: {str(e)}"
        except Exception as e:
            return False, f"Errore durante l'invio dell'email: {str(e)}"