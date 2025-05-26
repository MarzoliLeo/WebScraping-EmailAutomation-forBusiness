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
    all_emails = sender.extract_all_emails(df_json)

    if not all_emails:
        st.warning("⚠️ Nessun indirizzo email trovato, riprovare la ricerca.")
        return

    name_of_the_business = df_json.iloc[0].get("Nome Azienda")
    example_site = df_json.iloc[0].get("Sito Web")

    # Generazione opzionale del testo AI
    #if "email_body" not in st.session_state:
    st.session_state.email_body = ""  # inizialmente vuoto

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🤖 Genera Email con AI", use_container_width=True):
            with st.spinner("🧠 Generazione della mail..."):
                body = sender.generate_bulk_message(name_of_the_business, example_site)
                st.session_state.email_body = body
                st.success("✅ Email generata. Puoi modificarla prima dell'invio.")

    st.markdown("---")

    # Il form è SEMPRE visibile
    with st.form("email_form", clear_on_submit=False):
        subject = st.text_input(
            "Oggetto",
            "Proposta di collaborazione con eventuale finanziamento a fondo perduto - Metaphora",
            key="manual_subject"
        )
        message = st.text_area(
            "Corpo del Messaggio",
            st.session_state.email_body,
            height=250,
            key="manual_editable_message"
        )
        submitted = st.form_submit_button("📨 Invia Email")

        if submitted:
            with st.spinner("📤 Invio email in corso..."):
                results = []
                for email in all_emails:
                    success, status = sender.send_email(email, subject, message)
                    results.append((email, status))

            st.success("✅ Invio completato")
            for email, status in results:
                st.write(f"{email}: {status}")
