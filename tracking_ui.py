# tracker_ui.py
import streamlit as st
import pandas as pd
from tracker_logic import get_tracking_status
import time
import plotly.express as px


class EmailTrackerUI:
    def __init__(self):
        # Inizializza session_state per la cache degli alert e il timer
        # Questi non verranno più usati per visualizzare nella UI ma per la logica interna di auto-refresh
        if 'last_refresh_time_ui' not in st.session_state:
            st.session_state.last_refresh_time_ui = time.time()
        # Manteniamo tracking_data_cache per la logica degli alert nel ciclo di refresh
        if 'tracking_data_cache' not in st.session_state:
            st.session_state.tracking_data_cache = {}
        # Questo verrà usato per popolare la lista di log, non più per alert che spariscono
        if 'opening_logs' not in st.session_state:
            st.session_state.opening_logs = []


    def show_interface(self):
        st.header("📊 Stato Apertura Email (Tramite Click)")

        # Recupera i dati di tracciamento attuali dal server Flask
        tracking_data = get_tracking_status()

        # Processa e aggiungi nuovi eventi al log
        self._process_and_update_logs(tracking_data)

        # Aggiorna la cache dei dati DOPO aver processato gli alert per questa iterazione
        st.session_state.tracking_data_cache = tracking_data.copy()

        # Inizializza df_tracking con le colonne attese, anche se è vuoto
        expected_columns = [
            "ID Tracciamento", "Azienda", "Destinatario", "Stato",
            "Ora Invio", "Ora Apertura (o Click)"
        ]
        df_tracking = pd.DataFrame(columns=expected_columns)

        if not tracking_data:
            st.info("Nessuna email tracciata finora o impossibile connettersi al server di tracciamento.")
        else:
            display_data = []
            for tid, data in tracking_data.items():
                status = "Inviata"
                if data.get("opened_at"):
                    status = "Aperta"

                display_data.append({
                    "ID Tracciamento": tid,
                    "Azienda": data.get("company_name", "N/A"),
                    "Destinatario": data.get("recipient_email", "N/A"),
                    "Stato": status,
                    "Ora Invio": data.get("sent_at", "N/A"),
                    "Ora Apertura (o Click)": data.get("opened_at", "N/A")
                })
            df_tracking = pd.DataFrame(display_data)

            if not df_tracking.empty:
                df_tracking["Ora Invio"] = pd.to_datetime(df_tracking["Ora Invio"], errors='coerce')
                df_tracking["Ora Apertura (o Click)"] = pd.to_datetime(df_tracking["Ora Apertura (o Click)"], errors='coerce')

                df_tracking = df_tracking.sort_values(by="Ora Invio", ascending=False).reset_index(drop=True)

                df_tracking["Ora Invio"] = df_tracking["Ora Invio"].dt.strftime('%Y-%m-%d %H:%M:%S').fillna("N/A")
                df_tracking["Ora Apertura (o Click)"] = df_tracking["Ora Apertura (o Click)"].dt.strftime(
                    '%Y-%m-%d %H:%M:%S').fillna("N/A")


        # --- Rimosso: Alert "Email generata..." (dovrebbe essere gestito alla fonte se ancora presente) ---
        # Se questo alert verde proviene da `email_sender.py` o `app.py` in Streamlit,
        # è necessario pulire i messaggi di sessione o assicurarsi che non vengano generati qui.
        # Streamlit non ha un meccanismo diretto per "catturare" e rimuovere messaggi
        # da altre parti dell'applicazione se non vengono esplicitamente passati o gestiti.
        # La cosa più sicura è verificare il punto in cui quel "st.success" o "st.info" è chiamato
        # e condizionarlo alla pagina corretta o alla sessione.

        # --- Dashboard Statistiche ---
        st.subheader("Statistiche Generali")
        total_sent = len(df_tracking)
        total_opened = df_tracking[df_tracking["Stato"] == "Aperta"].shape[0]
        total_pending = total_sent - total_opened

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📧 Email Inviate", total_sent)
        with col2:
            st.metric("✅ Email Aperte", total_opened)
        with col3:
            st.metric("⏳ Email in Attesa", total_pending)

        if not df_tracking.empty:
            status_counts = df_tracking["Stato"].value_counts().reset_index()
            status_counts.columns = ['Stato', 'Conteggio']
            color_map = {
                "Aperta": '#2ca02c',
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


        # --- Riepilogo Dettagliato ---
        st.markdown("---")
        st.subheader("📬 Riepilogo Dettagliato")

        st.markdown("##### ✅ Email Aperte")
        df_opened = df_tracking[df_tracking["Stato"] == "Aperta"]
        if not df_opened.empty:
            st.dataframe(df_opened[['Azienda', 'Destinatario', 'Ora Invio', 'Ora Apertura (o Click)']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna email è stata ancora aperta.")

        st.markdown("##### ⏳ Email in Attesa di Apertura")
        df_pending = df_tracking[df_tracking["Stato"] == "Inviata"]
        if not df_pending.empty:
            st.dataframe(df_pending[['Azienda', 'Destinatario', 'Ora Invio']], use_container_width=True,
                         hide_index=True)
        else:
            st.info("Tutte le email inviate sono state aperte o non ci sono email in attesa.")

        # --- Log Eventi Recenti (sostituisce gli Alert) ---
        st.markdown("---")
        st.subheader("📝 Log Eventi Recenti")

        if st.session_state.opening_logs:
            # Mostra i log in ordine cronologico inverso (eventi più recenti in cima)
            for log_entry in reversed(st.session_state.opening_logs):
                st.markdown(log_entry)
        else:
            st.info("Nessun evento di apertura/click registrato di recente.")


    def _process_and_update_logs(self, current_tracking_data):
        # Questo metodo verrà chiamato ad ogni refresh per aggiornare la lista dei log
        for tid, data in current_tracking_data.items():
            previous_data = st.session_state.tracking_data_cache.get(tid, {})
            previous_opened_at = previous_data.get("opened_at")
            current_opened_at = data.get("opened_at")

            # Se l'email è stata appena aperta/cliccata e non è ancora nel log
            if current_opened_at and not previous_opened_at:
                log_message = (
                    f"**[{data.get('opened_at', 'N/A')}]** Email aperta (o cliccata) da "
                    f"**'{data.get('company_name', 'N/A')}'** "
                    f"({data.get('recipient_email', 'N/A')})."
                )
                # Aggiungi il log solo se non è già presente per evitare duplicati
                # (anche se il `not previous_opened_at` dovrebbe già prevenire la maggior parte dei duplicati)
                if log_message not in st.session_state.opening_logs:
                    st.session_state.opening_logs.append(log_message)