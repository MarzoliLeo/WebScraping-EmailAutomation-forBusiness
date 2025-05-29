# tracker_logic.py - Versione CORRETTA per tracciamento risposte (HTML invisibile)
import uuid
import time
import requests
import streamlit as st
from urllib.parse import quote_plus
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
import re
from datetime import datetime, timedelta, timezone

FLASK_TRACKER_BASE_URL = "http://127.0.0.1:5000"

from gmail_config import get_gmail_service


def generate_tracking_logic(recipient_email, company_name):
    """
    Genera un URL di tracking pixel unico e registra l'email con il server Flask.
    """
    tracking_id = str(uuid.uuid4())
    sent_at_timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    email_registration_data = {
        "tracking_id": tracking_id,
        "email_id": tracking_id,
        "recipient_email": recipient_email,
        "company_name": company_name,
        "sent_at": sent_at_timestamp
    }

    try:
        response = requests.post(f"{FLASK_TRACKER_BASE_URL}/register_email", json=email_registration_data, timeout=5)
        response.raise_for_status()
        print(f"Successfully registered email with tracker server: {response.json()}")
    except requests.exceptions.RequestException as e:
        st.error(
            f"Errore nel registrare l'email con il server di tracciamento: {e}. Assicurati che il server sia attivo e l'URL sia corretto.")
        print(f"Error registering email with tracker server: {e}")
        return None

    pixel_url = f"{FLASK_TRACKER_BASE_URL}/pixel/{tracking_id}.gif"
    return tracking_id, pixel_url


def generate_tracked_link(tracking_id, original_url):
    """
    Genera un URL che passa attraverso il server di tracciamento Flask prima di reindirizzare.
    """
    encoded_url = quote_plus(original_url)
    return f"{FLASK_TRACKER_BASE_URL}/click/{tracking_id}/{encoded_url}"


def get_tracking_status():
    """
    Recupera lo stato del tracciamento facendo una richiesta HTTP al server Flask.
    """
    try:
        response = requests.get(f"{FLASK_TRACKER_BASE_URL}/status", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Errore nel recuperare lo stato di tracciamento dal server: {e}. "
                 f"Verifica che il server Flask sia in esecuzione all'indirizzo '{FLASK_TRACKER_BASE_URL}'.")
        print(f"Error fetching tracking status from server: {e}")
        return {}


def _get_email_part_data(parts, mime_type):
    """Funzione ricorsiva per estrarre dati da parti specifiche di un'email."""
    for part in parts:
        if part['mimeType'] == mime_type and 'body' in part and 'data' in part['body']:
            try:
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            except Exception as decode_e:
                print(f"Errore decodifica {mime_type} : {decode_e}")
        if 'parts' in part:
            result = _get_email_part_data(part['parts'], mime_type)
            if result:
                return result
    return None


def check_for_replies_and_bounces():
    service = get_gmail_service()
    if not service:
        return

    all_tracked_emails = get_tracking_status()
    pending_emails = {
        tid: data for tid, data in all_tracked_emails.items()
        if data.get("status") not in ["replied", "bounced"]
    }

    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    query_timestamp = int(two_days_ago.timestamp())
    query = f"after:{query_timestamp}"

    try:
        results_inbox = service.users().messages().list(userId='me', q=query, labelIds=['INBOX'],
                                                        maxResults=100).execute()
        messages_inbox = results_inbox.get('messages', [])

        results_sent = service.users().messages().list(userId='me', q=query, labelIds=['SENT'],
                                                       maxResults=100).execute()
        messages_sent = results_sent.get('messages', [])

        all_new_messages = messages_inbox + messages_sent

        if not all_new_messages:
            print("Nessuna nuova email da processare negli ultimi 2 giorni.")
            return

        # Pattern regex per un UUID (versione 4)
        uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', re.IGNORECASE)

        for msg_summary in all_new_messages:
            msg_id = msg_summary['id']

            try:
                full_msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                headers = full_msg['payload']['headers']

                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '').lower()
                from_email = next((h['value'] for h in headers if h['name'] == 'From'), '').lower()

                in_reply_to = next((h['value'] for h in headers if h['name'] == 'In-Reply-To'), '')
                references = next((h['value'] for h in headers if h['name'] == 'References'), '')

                # Estrai sia il testo semplice che l'HTML per cercare l'UUID
                msg_body_plain = _get_email_part_data(full_msg['payload'].get('parts', []), 'text/plain') or \
                                 (_get_email_part_data([full_msg['payload']], 'text/plain') if 'body' in full_msg[
                                     'payload'] else '')
                msg_body_html = _get_email_part_data(full_msg['payload'].get('parts', []), 'text/html') or \
                                (_get_email_part_data([full_msg['payload']], 'text/html') if 'body' in full_msg[
                                    'payload'] else '')

                # --- LOGICA PER TRACCIARE RISPOSTE ---
                matched_reply_tracking_id = None

                # 1. Prova a estrarre UUID dagli header In-Reply-To e References (metodo originale)
                found_uuids_in_headers = set()
                found_uuids_in_headers.update(uuid_pattern.findall(in_reply_to))
                found_uuids_in_headers.update(uuid_pattern.findall(references))

                for tid_pending, data_pending in pending_emails.items():
                    if tid_pending in found_uuids_in_headers:
                        matched_reply_tracking_id = tid_pending
                        print(f"DEBUG: Match found in headers! Tracking ID: {matched_reply_tracking_id}")
                        break

                # 2. Se non trovato negli header, cerca nel corpo HTML (il nuovo metodo)
                if not matched_reply_tracking_id and msg_body_html:
                    # Pattern per trovare l'UUID all'interno del tag <p style="display: none;">
                    # Cerca <p style="display: none;">UUID</p>
                    invisible_tracking_pattern = re.compile(r'<p style="display: none;">([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})</p>', re.IGNORECASE)
                    found_uuids_in_body = invisible_tracking_pattern.findall(msg_body_html)

                    if found_uuids_in_body:
                        potential_tracking_id_from_body = found_uuids_in_body[0]  # Prendi il primo UUID trovato
                        for tid_pending, data_pending in pending_emails.items():
                            if tid_pending == potential_tracking_id_from_body:
                                matched_reply_tracking_id = tid_pending
                                print(f"DEBUG: Match found in body (hidden P tag)! Tracking ID: {matched_reply_tracking_id}")
                                break
                    else:
                        print(f"DEBUG: No UUID found in hidden P tag for message ID: {msg_id}")

                if matched_reply_tracking_id:
                    if pending_emails[matched_reply_tracking_id].get("replied_at") is None:
                        try:
                            response = requests.post(f"{FLASK_TRACKER_BASE_URL}/record_reply",
                                                     json={"tracking_id": matched_reply_tracking_id})
                            response.raise_for_status()
                            print(
                                f"Recorded reply for tracking ID: {matched_reply_tracking_id}. Server response: {response.json()}")
                            pending_emails[matched_reply_tracking_id]["replied_at"] = datetime.now(
                                timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                        except requests.exceptions.RequestException as e:
                            print(f"Error recording reply for {matched_reply_tracking_id}: {e}")
                else:
                    print(f"DEBUG: No reply tracking ID matched for message ID: {msg_id}")

                # --- LOGICA PER TRACCIARE RIMBALZI --- (Rimane invariata)
                is_bounce = False
                bounce_type = "unknown"
                bounce_reason = subject

                if "delivery status notification" in subject or "undelivered mail returned to sender" in subject or \
                        "mail delivery subsystem" in from_email or "mailer-daemon" in from_email:
                    is_bounce = True
                    if "permanent failure" in msg_body_plain.lower() or "address not found" in msg_body_plain.lower() or "no such user" in msg_body_plain.lower():
                        bounce_type = "hard"
                    elif "temporary failure" in msg_body_plain.lower() or "quota exceeded" in msg_body_plain.lower() or "mailbox full" in msg_body_plain.lower():
                        bounce_type = "soft"

                    bounce_recipient_email_found = None
                    original_recipient_header = next((h['value'] for h in headers if h['name'] == 'Original-Recipient'),
                                                     '')
                    if original_recipient_header:
                        match_email = re.search(r'rfc822;\s*(\S+@\S+)', original_recipient_header)
                        if match_email:
                            bounce_recipient_email_found = match_email.group(1)

                    if not bounce_recipient_email_found:
                        email_in_body_match = re.search(
                            r'(?:To|Recipient):\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', msg_body_plain,
                            re.IGNORECASE)
                        if email_in_body_match:
                            bounce_recipient_email_found = email_in_body_match.group(1)
                        else:
                            email_in_body_match = re.search(r'(\S+@\S+\.\S+)', msg_body_plain)
                            if email_in_body_match:
                                bounce_recipient_email_found = email_in_body_match.group(1)

                    matched_bounce_tracking_id = None
                    if bounce_recipient_email_found:
                        for tid, data in pending_emails.items():
                            if data["recipient_email"].lower() == bounce_recipient_email_found.lower() and data.get(
                                    "bounced_at") is None:
                                matched_bounce_tracking_id = tid
                                break

                    if is_bounce and matched_bounce_tracking_id:
                        if pending_emails[matched_bounce_tracking_id].get("bounced_at") is None:
                            try:
                                response = requests.post(f"{FLASK_TRACKER_BASE_URL}/record_bounce", json={
                                    "tracking_id": matched_bounce_tracking_id,
                                    "bounce_type": bounce_type,
                                    "bounce_reason": bounce_reason
                                })
                                response.raise_for_status()
                                print(
                                    f"Recorded bounce for tracking ID: {matched_bounce_tracking_id}. Server response: {response.json()}")
                                pending_emails[matched_bounce_tracking_id]["bounced_at"] = datetime.now(
                                    timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                            except requests.exceptions.RequestException as e:
                                print(f"Error recording bounce for {matched_bounce_tracking_id}: {e}")

            except Exception as e_msg_proc:
                print(f"Errore durante il processamento del messaggio {msg_id}: {e_msg_proc}")

    except Exception as e:
        st.error(f"Errore durante il controllo principale di risposte e rimbalzi: {e}")
        print(f"Error checking for replies/bounces: {e}")