# email_ui.py

import streamlit as st
import pandas as pd
import json
from email_sender import EmailSender

def show_email_interface(json_string_data=None, authenticated_user_email=None): # Add authenticated_user_email parameter
    st.header("📧 Invia Email ai Contatti")

    if not authenticated_user_email:
        st.warning("Per inviare email, devi prima connettere il tuo account Gmail dalla sidebar.")
        return

    if json_string_data is None:
        uploaded_file = st.file_uploader("Carica un file JSON con i contatti validi", type=["json"])
        if uploaded_file is None:
            return
        content = uploaded_file.read().decode("utf-8")
    else:
        content = json_string_data

    # Parse the JSON string
    try:
        data = json.loads(content)
        df_json = pd.DataFrame(data)
    except json.JSONDecodeError as e:
        st.error(f"❌ Errore nel parsing del file JSON: {e}")
        return

    st.dataframe(df_json)

    sender = EmailSender(authenticated_user_email) # Pass authenticated_user_email to EmailSender

    if "email_body_template" not in st.session_state:
        st.session_state.email_body_template = ""

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("🤖 Genera Email con AI (Template)", use_container_width=True):
            with st.spinner("🧠 Generazione della mail template..."):
                first_company_name = df_json.iloc[0].get("Nome Azienda", "un'azienda")
                first_example_site = df_json.iloc[0].get("Sito Web", "il loro sito web")

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
                for index, row in df_json.iterrows():
                    recipient_email_str = row.get("Email trovate")
                    company_name_for_email = row.get("Nome Azienda", "Azienda Sconosciuta")
                    example_site_for_email = row.get("Sito Web", "sito web")

                    emails_to_send_for_row = [e.strip() for e in recipient_email_str.split(",") if
                                              e.strip()] if isinstance(recipient_email_str, str) else []

                    if not emails_to_send_for_row:
                        results.append(
                            (f"Riga {index + 1} ({company_name_for_email})", "Nessuna email valida trovata."))
                        continue

                    for email in emails_to_send_for_row:
                        success, status = sender.send_email(email, subject, message_template,
                                                            company_name_for_email)
                        results.append((f"{company_name_for_email} ({email})", status))

            st.success("✅ Invio completato")
            for company_email_info, status in results:
                st.write(f"{company_email_info}: {status}")