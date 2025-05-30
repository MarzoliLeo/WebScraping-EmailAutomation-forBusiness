# email_ui.py
import streamlit as st
import pandas as pd
import json
from email_sender import EmailSender


def show_email_interface(json_string_data=None):
    st.header("📧 Invia Email ai Contatti")

    if json_string_data is None:
        uploaded_file = st.file_uploader("Carica un file JSON con i contatti validi", type=["json"])
        if uploaded_file is None:
            return
        content = uploaded_file.read().decode("utf-8")
    else:
        content = json_string_data

    # Parso il JSON da stringa
    try:
        data = json.loads(content)
        df_json = pd.DataFrame(data)
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nel parsing del file JSON: {e}")
        return

    st.dataframe(df_json)

    sender = EmailSender()

    # Rimuovi queste righe, in quanto non sono più necessarie qui globalmente
    # name_of_the_business = df_json.iloc[0].get("Nome Azienda")
    # example_site = df_json.iloc[0].get("Sito Web")

    if "email_body_template" not in st.session_state:  # Rinominato per chiarezza, sarà un template
        st.session_state.email_body_template = ""

    col1, col2 = st.columns([1, 2])
    with col1:
        # La generazione dell'email con AI ora dovrebbe essere un template generico o usare il primo elemento come esempio
        # Per semplicità, useremo un placeholder o il primo elemento per generare il template iniziale
        # Possiamo prendere il primo elemento come base per generare un'email di esempio per l'utente da modificare.
        # Oppure, se vuoi una mail generica, non passare name_of_the_business e example_site qui.

        # Per evitare che il template sia troppo specifico al primo elemento,
        # generiamo un template generico. L'AI genererà un testo che l'utente può poi personalizzare.
        # Se si vuole personalizzazione del template, serve un input esplicito per l'AI su quale azienda basarlo.
        # Per ora, usiamo il primo elemento solo per il prompt dell'AI per dare un'idea del contesto.
        if st.button("🤖 Genera Email con AI (Template)", use_container_width=True):
            with st.spinner("🧠 Generazione della mail template..."):
                # Prendo il primo elemento del JSON per dare un contesto all'AI,
                # ma l'email generata sarà un TEMPLATE.
                first_company_name = df_json.iloc[0].get("Nome Azienda", "un'azienda")
                first_example_site = df_json.iloc[0].get("Sito Web", "il loro sito web")

                # La funzione generate_bulk_message è già progettata per questo.
                body_template = sender.generate_bulk_message(first_company_name, first_example_site)
                st.session_state.email_body_template = body_template
                st.success("✅ Email template generato. Puoi modificarlo e verrà usato per tutte le email.")

    st.markdown("---")

    with st.form("email_form", clear_on_submit=False):
        subject = st.text_input(
            "Oggetto",
            "Proposta di collaborazione con eventuale finanziamento a fondo perduto - Metaphora",
            key="manual_subject"
        )
        # Il corpo del messaggio ora è un template modificabile
        message_template = st.text_area(
            "Corpo del Messaggio (Template, personalizzabile automaticamente per ogni invio)",
            st.session_state.email_body_template,
            height=250,
            key="manual_editable_message"
        )
        submitted = st.form_submit_button("📨 Invia Email")

        if submitted:
            with st.spinner("📤 Invio email in corso..."):
                results = []
                # Iteriamo su ogni riga del DataFrame
                for index, row in df_json.iterrows():
                    recipient_email_str = row.get("Email trovate")  # Ottieni la stringa delle email
                    company_name_for_email = row.get("Nome Azienda",
                                                     "Azienda Sconosciuta")  # Ottieni il nome dell'azienda specifico
                    example_site_for_email = row.get("Sito Web", "sito web")  # Ottieni il sito web specifico

                    # Estrai le email singole, come fa EmailSender.extract_all_emails
                    emails_to_send_for_row = [e.strip() for e in recipient_email_str.split(",") if
                                              e.strip()] if isinstance(recipient_email_str, str) else []

                    if not emails_to_send_for_row:
                        results.append(
                            (f"Riga {index + 1} ({company_name_for_email})", "Nessuna email valida trovata."))
                        continue

                    # Personalizza il messaggio per questa specifica azienda
                    # Usiamo il template e lo sostituiamo con i dati dell'azienda corrente.
                    # Questo è un esempio basilare, potresti volere un sistema di template più robusto.
                    # Per ora, assumiamo che il template possa contenere placeholder come {NomeAzienda} o {SitoWeb}
                    # ESEMPIO SEMPLICE DI PERSONALIZZAZIONE (da migliorare se necessario)
                    # Ad esempio, il prompt di generate_bulk_message è già abbastanza generico,
                    # e la personalizzazione avviene nel corpo generato che già cita il nome azienda/sito.
                    # Se il template è generico, lo usiamo così com'è per ogni email,
                    # ma il tracking sarà specifico per azienda.
                    # Se l'utente ha modificato il template, lo inviamo così come sta.

                    # La logica di generazione del messaggio è già gestita da EmailSender.generate_bulk_message
                    # che viene chiamato all'inizio per popolare il template.
                    # Se l'utente modifica il template, inviamo quello.

                    # Se vuoi personalizzare ulteriormente il messaggio per ogni email,
                    # devi fare una sostituzione di placeholder qui. Ad esempio:
                    # personalized_message = message_template.replace("{NomeAzienda}", company_name_for_email)
                    # personalized_message = personalized_message.replace("{SitoWeb}", example_site_for_email)

                    # Per il tuo caso, la modifica più importante è assicurarsi che company_name_for_email
                    # venga passato correttamente per il tracking.

                    for email in emails_to_send_for_row:
                        # Passa il nome dell'azienda specifico per questa riga al metodo send_email
                        success, status = sender.send_email(email, subject, message_template,
                                                            company_name_for_email)  # <--- QUESTA È LA MODIFICA CHIAVE
                        results.append((f"{company_name_for_email} ({email})", status))

            st.success("✅ Invio completato")
            for company_email_info, status in results:
                st.write(f"{company_email_info}: {status}")