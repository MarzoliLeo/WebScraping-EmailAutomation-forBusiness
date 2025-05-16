# email_ui.py
import streamlit as st
import pandas as pd
from email_sender import EmailSender


def show_email_interface():
    st.header("📧 Invia Email ai Contatti")
    uploaded_file = st.file_uploader("Carica un file JSON con i contatti validi", type=["json"])

    if uploaded_file:
        df_json = pd.read_json(uploaded_file)
        st.dataframe(df_json)

        sender = EmailSender()
        all_emails = sender.extract_all_emails(df_json)

        if all_emails:
            example_site = df_json.iloc[0]["Sito Web"]
            if "generated_email" not in st.session_state:
                with st.spinner("🧠 Generazione della mail..."):
                    st.session_state.generated_email = sender.generate_bulk_message(example_site)

            subject = "Proposta di Collaborazione"
            st.success("✅ Email generata. Verrà inviata a tutti i contatti elencati.")
            message = st.text_area("Messaggio", st.session_state.generated_email, height=250,
                                   key="manual_editable_message")

            if st.button("📨 Invia Email a Tutti"):
                with st.spinner("📤 Invio email in corso..."):
                    results = []
                    for email in all_emails:
                        success, status = sender.send_email(email, subject, message)
                        results.append((email, status))
                st.success("✅ Invio completato")
                for email, status in results:
                    st.write(f"{email}: {status}")
        else:
            st.warning("Nessun indirizzo email trovato nel file caricato.")
