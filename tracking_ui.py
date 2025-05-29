# tracker_ui.py
import streamlit as st
import pandas as pd
from tracker_logic import get_tracking_status
import time
import plotly.express as px


class EmailTrackerUI:
    def __init__(self):
        if 'last_refresh_time' not in st.session_state:
            st.session_state.last_refresh_time = time.time()
        if 'tracking_data_cache' not in st.session_state:
            st.session_state.tracking_data_cache = {}

    def show_interface(self):
        st.header("📊 Stato Apertura Email (Tramite Click)")  # Aggiorna il titolo

        refresh_interval_seconds = 3
        current_time = time.time()

        if st.button("🔄 Aggiorna Dati Tracciamento"):
            st.session_state.last_refresh_time = current_time
            st.cache_data.clear()
            st.rerun()

        if (current_time - st.session_state.last_refresh_time) > refresh_interval_seconds:
            st.session_state.last_refresh_time = current_time
            st.cache_data.clear()
            st.rerun()

        st.markdown(
            f"Ultimo aggiornamento dati: **{time.strftime('%H:%M:%S', time.localtime(st.session_state.last_refresh_time))}**")

        tracking_data = get_tracking_status()
        st.session_state.tracking_data_cache = tracking_data.copy()

        if not tracking_data:
            st.info("Nessuna email tracciata finora o impossibile connettersi al server di tracciamento.")
            return

        display_data = []
        for tid, data in tracking_data.items():
            status = "Inviata"
            # Lo stato "Aperta" ora include i click (se opened_at è non nullo, che ora include i click)
            if data.get("opened_at"):
                status = "Aperta"

            display_data.append({
                "ID Tracciamento": tid,
                "Azienda": data.get("company_name", "N/A"),
                "Destinatario": data.get("recipient_email", "N/A"),
                "Stato": status,
                "Ora Invio": data.get("sent_at", "N/A"),
                "Ora Apertura (o Click)": data.get("opened_at", "N/A")  # Rinomina per chiarezza
                # Non mostriamo direttamente "Ora Click" nella tabella principale se lo stato è "Aperta"
                # Ma possiamo usarlo internamente per gli alert o altre analisi se necessario.
            })

        df_tracking = pd.DataFrame(display_data)

        df_tracking["Ora Invio"] = pd.to_datetime(df_tracking["Ora Invio"], errors='coerce')
        df_tracking["Ora Apertura (o Click)"] = pd.to_datetime(df_tracking["Ora Apertura (o Click)"], errors='coerce')

        df_tracking = df_tracking.sort_values(by="Ora Invio", ascending=False).reset_index(drop=True)

        df_tracking["Ora Invio"] = df_tracking["Ora Invio"].dt.strftime('%Y-%m-%d %H:%M:%S').fillna("N/A")
        df_tracking["Ora Apertura (o Click)"] = df_tracking["Ora Apertura (o Click)"].dt.strftime(
            '%Y-%m-%d %H:%M:%S').fillna("N/A")

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

        # Grafico a torta per lo stato delle email
        status_counts = df_tracking["Stato"].value_counts().reset_index()
        status_counts.columns = ['Stato', 'Conteggio']
        color_map = {
            "Aperta": '#2ca02c',  # Verde per le aperture (ora include i click)
            "Inviata": '#1f77b4'  # Blu per le inviate
        }
        fig_pie = px.pie(status_counts, values='Conteggio', names='Stato',
                         title='Distribuzione Stato Email',
                         color='Stato',
                         color_discrete_map=color_map,
                         hole=0.3)
        st.plotly_chart(fig_pie, use_container_width=True)

        # --- Riepilogo Dettagliato ---
        st.markdown("---")
        st.subheader("📬 Riepilogo Dettagliato")

        # Tabella per email aperte (ora include quelle cliccate)
        st.markdown("##### ✅ Email Aperte")
        df_opened = df_tracking[df_tracking["Stato"] == "Aperta"]
        if not df_opened.empty:
            st.dataframe(df_opened[['Azienda', 'Destinatario', 'Ora Invio', 'Ora Apertura (o Click)']],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna email è stata ancora aperta.")

        # Tabella per email in attesa
        st.markdown("##### ⏳ Email in Attesa di Apertura")
        df_pending = df_tracking[df_tracking["Stato"] == "Inviata"]
        if not df_pending.empty:
            st.dataframe(df_pending[['Azienda', 'Destinatario', 'Ora Invio']], use_container_width=True,
                         hide_index=True)
        else:
            st.info("Tutte le email inviate sono state aperte o non ci sono email in attesa.")

        # --- Alert di Apertura (Nuovi Eventi) ---
        st.markdown("---")
        st.subheader("🔔 Alert di Apertura (Nuovi Eventi)")

        new_opens = []
        for tid, data in tracking_data.items():
            previous_status_opened = st.session_state.tracking_data_cache.get(tid, {}).get("opened_at") is not None
            current_status_opened = data.get("opened_at") is not None

            # Un nuovo alert di apertura si verifica se prima non era aperta e ora lo è
            if current_status_opened and not previous_status_opened and st.session_state.get(f"alert_opened_{tid}",
                                                                                             False) is False:
                new_opens.append(data)
                st.session_state[f"alert_opened_{tid}"] = True

        if new_opens:
            for open_info in new_opens:
                st.success(
                    f"🔔 **ALERT!** Email aperta (o cliccata) da **'{open_info.get('company_name', 'N/A')}'** "
                    f"({open_info.get('recipient_email', 'N/A')}) alle **{open_info.get('opened_at', 'N/A')}**!"
                )
        else:
            st.info("Nessun nuovo alert di apertura.")