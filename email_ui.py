# email_ui.py
import streamlit as st
import pandas as pd
import json
from email_sender import EmailSender

def show_email_interface():
    st.header("📧 Invia Email ai Contatti")
    uploaded_file = st.file_uploader("Carica un file JSON con i contatti validi", type=["json"])

    if uploaded_file is not None:
        # Leggi il contenuto come stringa di testo
        content = uploaded_file.read().decode("utf-8")

        # Parso il JSON da stringa
        try:
            data = json.loads(content)
            df_json = pd.DataFrame(data)
        except json.JSONDecodeError as e:
            st.error(f"❌ Errore nel parsing del file JSON: {e}")
            return

        st.dataframe(df_json)

        sender = EmailSender()
        all_emails = sender.extract_all_emails(df_json)

        if all_emails:
            name_of_the_business = df_json.iloc[0].get("Nome Azienda")
            example_site = df_json.iloc[0].get("Sito Web")

            if "email_subject" not in st.session_state or "email_body" not in st.session_state:
                with st.spinner("🧠 Generazione della mail..."):
                    body = sender.generate_bulk_message(name_of_the_business, example_site)
                    st.session_state.email_body = body

            st.success("✅ Email generata automaticamente. Puoi modificarla prima dell'invio.")

            with st.form("email_form"):
                subject = st.text_input("Oggetto", "Proposta di collaborazione con eventuale finanziamento a fondo perduto - Metaphora", key="manual_subject")
                message = st.text_area("Corpo del Messaggio", st.session_state.email_body, height=250,
                                       key="manual_editable_message")
                submitted = st.form_submit_button("📨 Invia Email a Tutti")

                if submitted:
                    with st.spinner("📤 Invio email in corso..."):
                        results = []
                        for email in all_emails:
                            success, status = sender.send_email(email, subject, message)
                            results.append((email, status))

                    st.success("✅ Invio completato")
                    for email, status in results:
                        st.write(f"{email}: {status}")
        else:
            st.warning("⚠️ Nessun indirizzo email trovato nel file caricato.")
