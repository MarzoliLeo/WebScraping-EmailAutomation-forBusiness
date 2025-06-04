# tracking_ui.py (AGGIORNATO)
import streamlit as st
import pandas as pd
import time
import plotly.express as px
import requests # Importa requests

# Modifica per puntare all'URL del server Flask su PythonAnywhere
FLASK_TRACKER_BASE_URL = "https://marzoli95.pythonanywhere.com"

# La funzione get_tracking_status e generate_tracked_link sono importate da tracker_logic
# e già usano FLASK_TRACKER_BASE_URL, quindi non necessitano modifiche qui.
from tracker_logic import get_tracking_status

# Non importare più check_for_replies_and_bounces direttamente qui
# from tracker_logic import check_for_replies_and_bounces


class EmailTrackerUI:
    def __init__(self):
        if 'tracking_data_cache' not in st.session_state:
            st.session_state.tracking_data_cache = {}
        if 'opening_logs' not in st.session_state:
            st.session_state.opening_logs = []
        if 'last_gmail_check_time' not in st.session_state:
            st.session_state.last_gmail_check_time = time.time()


    def show_interface(self):
        st.header("📊 Stato Apertura Email (Tramite Click)")

        # Controllo periodico per risposte e rimbalzi (meno frequente dell'UI refresh)
        # Questa chiamata ora DEVE essere fatta al server Flask
        gmail_check_interval_seconds = 30 # Controlla Gmail ogni 60 secondi
        current_time_for_gmail_check = time.time()
        if (current_time_for_gmail_check - st.session_state.last_gmail_check_time) > gmail_check_interval_seconds:
            st.session_state.last_gmail_check_time = current_time_for_gmail_check
            print(f"[{time.strftime('%H:%M:%S')}] Eseguo controllo risposte e rimbalzi da Gmail (tramite server Flask)...")

            # Esegui la richiesta al server Flask per controllare le email
            user_email = st.session_state.get("authenticated_user_email")
            if user_email:
                try:
                    response = requests.post(f"{FLASK_TRACKER_BASE_URL}/check_gmail_status_for_user", json={"user_email": user_email})
                    response.raise_for_status()
                    print(f"Server Flask ha controllato le email per {user_email}: {response.json().get('message')}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Errore nel richiedere il controllo email al server Flask: {e}")
            else:
                st.warning("Nessun utente autenticato. Il controllo delle risposte/rimbalzi di Gmail non può essere eseguito.")

        tracking_data = get_tracking_status() # Questa funzione chiama già il Flask server

        # Processa e aggiungi nuovi eventi al log
        self._process_and_update_logs(tracking_data)

        # Aggiorna la cache dei dati DOPO aver processato gli alert per questa iterazione
        st.session_state.tracking_data_cache = tracking_data.copy()

        # Inizializza df_tracking con le colonne attese, anche se è vuoto
        expected_columns = [
            "ID Tracciamento", "Azienda", "Destinatario", "Stato",
            "Ora Invio", "Ora Apertura (o Click)", "Ora Risposta", "Ora Rimbalzo",
            "Tipo Rimbalzo", "Motivo Rimbalzo"
        ]
        df_tracking = pd.DataFrame(columns=expected_columns)

        if not tracking_data:
            st.info("Nessuna email tracciata finora o impossibile connettersi al server di tracciamento.")
        else:
            display_data = []
            for tid, data in tracking_data.items():
                status = "Inviata"
                if data.get("bounced_at"): # Priorità al rimbalzo
                    status = "Rimbalzata"
                elif data.get("replied_at"): # Poi la risposta
                    status = "Risposta"
                elif data.get("opened_at"): # Poi l'apertura/click
                    status = "Aperta"

                display_data.append({
                    "ID Tracciamento": tid,
                    "Azienda": data.get("company_name", "N/A"), # Assicurati che company_name sia corretto nel JSON
                    "Destinatario": data.get("recipient_email", "N/A"),
                    "Stato": status,
                    "Ora Invio": data.get("sent_at", "N/A"),
                    "Ora Apertura (o Click)": data.get("opened_at", "N/A"),
                    "Ora Risposta": data.get("replied_at", "N/A"),
                    "Ora Rimbalzo": data.get("bounced_at", "N/A"),
                    "Tipo Rimbalzo": data.get("bounce_type", "N/A"),
                    "Motivo Rimbalzo": data.get("bounce_reason", "N/A")
                })
            df_tracking = pd.DataFrame(display_data)

            if not df_tracking.empty:
                df_tracking["Ora Invio"] = pd.to_datetime(df_tracking["Ora Invio"], errors='coerce')
                df_tracking["Ora Apertura (o Click)"] = pd.to_datetime(df_tracking["Ora Apertura (o Click)"], errors='coerce')
                df_tracking["Ora Risposta"] = pd.to_datetime(df_tracking["Ora Risposta"], errors='coerce')
                df_tracking["Ora Rimbalzo"] = pd.to_datetime(df_tracking["Ora Rimbalzo"], errors='coerce')

                df_tracking = df_tracking.sort_values(by="Ora Invio", ascending=False).reset_index(drop=True)

                df_tracking["Ora Invio"] = df_tracking["Ora Invio"].dt.strftime('%Y-%m-%d %H:%M:%S').fillna("N/A")
                df_tracking["Ora Apertura (o Click)"] = df_tracking["Ora Apertura (o Click)"].dt.strftime(
                    '%Y-%m-%d %H:%M:%S').fillna("N/A")
                df_tracking["Ora Risposta"] = df_tracking["Ora Risposta"].dt.strftime('%Y-%m-%d %H:%M:%S').fillna("N/A")
                df_tracking["Ora Rimbalzo"] = df_tracking["Ora Rimbalzo"].dt.strftime('%Y-%m-%d %H:%M:%S').fillna("N/A")


        # --- Dashboard Statistiche --- (invariata)
        st.subheader("Statistiche Generali")
        total_sent = len(df_tracking)
        total_opened = df_tracking[df_tracking["Stato"] == "Aperta"].shape[0]
        total_replied = df_tracking[df_tracking["Stato"] == "Risposta"].shape[0]
        total_bounced = df_tracking[df_tracking["Stato"] == "Rimbalzata"].shape[0]
        total_pending = total_sent - total_opened - total_replied - total_bounced

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📧 Inviate", total_sent)
        with col2:
            st.metric("✅ Aperte", total_opened)
        with col3:
            st.metric("↩️ Risposte", total_replied)
        with col4:
            st.metric("📭 Rimbalzi", total_bounced)
        with col5:
            st.metric("⏳ In Attesa", total_pending)

        if not df_tracking.empty:
            status_counts = df_tracking["Stato"].value_counts().reset_index()
            status_counts.columns = ['Stato', 'Conteggio']
            color_map = {
                "Aperta": '#2ca02c',
                "Risposta": '#00ffcc',
                "Rimbalzata": '#d62728',
                "Inviata": '#1f77b4'
            }
            fig_pie = px.pie(status_counts, values='Conteggio', names='Stato',
                             title='Distribuzione Stato Email',
                             color='Stato',
                             color_discrete_map=color_map,
                             hole=0.3)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Nessun dato per il grafico a torta.")


        # --- Riepilogo Dettagliato --- (invariata)
        st.markdown("---")
        st.subheader("📬 Riepilogo Dettagliato")

        st.markdown("##### ↩️ Email con Risposta")
        df_replied = df_tracking[df_tracking["Stato"] == "Risposta"]
        if not df_replied.empty:
            st.dataframe(df_replied[['Azienda', 'Destinatario', 'Ora Invio', 'Ora Risposta']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna email ha ricevuto una risposta.")

        st.markdown("##### 📭 Email Rimbalzate")
        df_bounced = df_tracking[df_tracking["Stato"] == "Rimbalzata"]
        if not df_bounced.empty:
            st.dataframe(df_bounced[['Azienda', 'Destinatario', 'Ora Invio', 'Ora Rimbalzo', 'Tipo Rimbalzo', 'Motivo Rimbalzo']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna email è rimbalzata.")

        st.markdown("##### ✅ Email Aperte (non Risposte/Rimbalzate)")
        df_opened = df_tracking[df_tracking["Stato"] == "Aperta"]
        if not df_opened.empty:
            st.dataframe(df_opened[['Azienda', 'Destinatario', 'Ora Invio', 'Ora Apertura (o Click)']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna email è stata aperta.")

        st.markdown("##### ⏳ Email in Attesa")
        df_pending = df_tracking[df_tracking["Stato"] == "Inviata"]
        if not df_pending.empty:
            st.dataframe(df_pending[['Azienda', 'Destinatario', 'Ora Invio']], use_container_width=True,
                         hide_index=True)
        else:
            st.info("Tutte le email inviate hanno uno stato finale (aperta, risposta, rimbalzata).")

        # --- Log Eventi Recenti --- (invariato)
        st.markdown("---")
        st.subheader("📝 Log Eventi Recenti")

        if st.session_state.opening_logs:
            for log_entry in reversed(st.session_state.opening_logs):
                st.markdown(log_entry)
        else:
            st.info("Nessun evento di apertura/click/risposta/rimbalzo registrato di recente.")


    def _process_and_update_logs(self, current_tracking_data):
        for tid, data in current_tracking_data.items():
            previous_data = st.session_state.tracking_data_cache.get(tid, {})

            # Log per Apertura/Click
            previous_opened_at = previous_data.get("opened_at")
            current_opened_at = data.get("opened_at")
            if current_opened_at and not previous_opened_at:
                log_message = (
                    f"**[{data.get('opened_at', 'N/A')}]** Email aperta (o cliccata) da "
                    f"**'{data.get('company_name', 'N/A')}'** "
                    f"({data.get('recipient_email', 'N/A')})."
                )
                if log_message not in st.session_state.opening_logs:
                    st.session_state.opening_logs.append(log_message)

            # Log per Risposta
            previous_replied_at = previous_data.get("replied_at")
            current_replied_at = data.get("replied_at")
            if current_replied_at and not previous_replied_at:
                log_message = (
                    f"**[{data.get('replied_at', 'N/A')}]** **RISPOSTA RICEVUTA** da "
                    f"**'{data.get('company_name', 'N/A')}'** "
                    f"({data.get('recipient_email', 'N/A')})."
                )
                if log_message not in st.session_state.opening_logs:
                    st.session_state.opening_logs.append(log_message)

            # Log per Rimbalzo
            previous_bounced_at = previous_data.get("bounced_at")
            current_bounced_at = data.get("bounced_at")
            if current_bounced_at and not previous_bounced_at:
                log_message = (
                    f"**[{data.get('bounced_at', 'N/A')}]** **RIMBALZO RILEVATO** per "
                    f"**'{data.get('recipient_email', 'N/A')}'** "
                    f"({data.get('bounce_type', 'N/A')}: {data.get('bounce_reason', 'N/A')})."
                )
                if log_message not in st.session_state.opening_logs:
                    st.session_state.opening_logs.append(log_message)