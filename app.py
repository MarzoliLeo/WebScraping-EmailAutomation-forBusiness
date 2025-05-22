import streamlit as st
import pandas as pd
from urllib.parse import urlparse
import cloudscraper
from bs4 import BeautifulSoup
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from utils import clean_valid_emails, EMAIL_CANDIDATE_REGEX, PRIORITY_KEYWORDS
from utils_llm import call_gemini_flash
from email_ui import show_email_interface
from googlesearch import search

st.set_page_config(page_title="Trova Clienti", layout="wide")

PARTITA_IVA_REGEX = r"(IT)?\s?\d{11}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False},
    disableCloudflareV1=True
)

if "start_email_flow" not in st.session_state:
    st.session_state.start_email_flow = False
if "email_json_data" not in st.session_state:
    st.session_state.email_json_data = None


def extract_emails_and_piva(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    mailtos = [a.get("href")[7:] for a in soup.find_all("a", href=True) if a.get("href", "").startswith("mailto:")]
    text = soup.get_text().lower()
    text_emails = re.findall(EMAIL_CANDIDATE_REGEX, text)
    partita_iva = re.search(PARTITA_IVA_REGEX, text)

    header = soup.find("header")
    footer = soup.find("footer")
    header_emails = re.findall(EMAIL_CANDIDATE_REGEX, header.get_text().lower()) if header else []
    footer_emails = re.findall(EMAIL_CANDIDATE_REGEX, footer.get_text().lower()) if footer else []

    all_emails = list(set(mailtos + text_emails + header_emails + footer_emails))
    filtered = clean_valid_emails(all_emails)
    filtered.sort(key=lambda e: (not any(k in e for k in PRIORITY_KEYWORDS), e))

    return filtered[:3], bool(partita_iva)

def try_common_contact_pages(base_url):
    contact_paths = ["/contatti", "/contact", "/about", "/chi-siamo", "/contact-us/"]
    found_emails, statuses, found_piva = [], [], False

    for path in contact_paths:
        contact_url = base_url.rstrip("/") + path
        try:
            resp = scraper.get(contact_url, timeout=10)
            if resp.status_code == 200:
                emails, has_piva = extract_emails_and_piva(resp.text)
                found_emails += emails
                found_piva = found_piva or has_piva
                statuses.append(f"{path}: ok")
            else:
                statuses.append(f"{path}: {resp.status_code} - {resp.reason}")
        except Exception as e:
            statuses.append(f"{path}: errore - {str(e)}")

    return list(set(found_emails)), found_piva, statuses

def extract_emails_from_url(url):
    try:
        response = scraper.get(url, timeout=10, headers=HEADERS, allow_redirects=True)
        if response.status_code != 200:
            return [], f"Errore HTTP {response.status_code} - {response.reason} ({url})"

        emails, has_piva = extract_emails_and_piva(response.text)
        if emails and has_piva:
            return emails, "Email e P.IVA trovati nella home page"

        contact_emails, found_piva, contact_statuses = try_common_contact_pages(url)
        if contact_emails and found_piva:
            return contact_emails, "Email e P.IVA trovati nelle pagine di contatto"

        return [], f"Nessuna combinazione valida trovata ({', '.join(contact_statuses)})"

    except Exception as e:
        return [], f"Errore durante l'accesso a {url}: {str(e)}"

def generate_company_list_prompt(settore, regione, dimensione, exclude_names):
    exclude_str = ", ".join(exclude_names) if exclude_names else "nessuno"
    return (
        f"Elenca esattamente 10 piccole aziende italiane di {settore.lower()}, "
        f"con meno di {dimensione} dipendenti, situate in {regione}. "
        f"Se possibile, includi il sito web. Evita questi nomi: {exclude_str}.\n"
        f"Formato: <Nome Azienda> - <Sito Web>\n"
        f"Esempio:\nABC Formazione - www.abcformazione.it\nNextLab Srl - www.nextlab.it\n"
        f"--- Inizio elenco ---"
    )


def find_site_by_name(name):
    try:
        query = f"{name} sito ufficiale"
        for url in search(query, num_results=5):
            if any(social in url for social in ["facebook", "linkedin", "instagram"]):
                continue
            if re.match(r"https?://(www\.)?[a-zA-Z0-9\-]+\.[a-z]{2,}", url):
                return url
    except Exception:
        pass
    return None


def show_scraper_interface():
    st.title("🔍 Ricerca Clienti Aziendali + Email")

    if "data_utili" not in st.session_state:
        st.session_state.data_utili = []
    if "data_scartati" not in st.session_state:
        st.session_state.data_scartati = []

    with st.form(key="filtro_form"):
        settore = st.text_input("Settore (es. Formazione professionale)")
        regione = st.text_input("Regione (es. Abruzzo)")
        dimensione = st.number_input("Numero massimo di dipendenti", min_value=1, max_value=1000, value=50, step=1)
        #codice_ateco = st.selectbox("Codice ATECO", ["", "62.01", "63.11", "72.10", "73.11", "74.10", "74.90", "80.10", "82.99"])
        max_results = st.slider("Numero di risultati positivi", 10, 100, 10)
        submitted = st.form_submit_button("Cerca Clienti")

    if submitted:
        found_names = set()
        data_utili, data_scartati = [], []
        lock = threading.Lock()
        progress_bar = st.progress(0)
        st.info("⏳ Ricerca in corso...")

        debug_log = st.empty()
        debug_lines = []
        log_lock = threading.Lock()

        def log(message):
            with log_lock:
                debug_lines.append(message)

        max_iterations = 10
        iteration = 0
        while len(data_utili) < max_results and iteration < max_iterations:
            iteration += 1

            prompt = generate_company_list_prompt(settore, regione, dimensione, list(found_names))
            log(f"🔁 Nuovo prompt LLM con {len(found_names)} nomi esclusi")
            output = call_gemini_flash(prompt)
            lines = output.strip().splitlines()

            companies = []
            for line in lines:
                if not line.strip():
                    continue
                text = line.strip()
                if not text:
                    continue
                # split in nome e sito
                if "-" in text:
                    name_part, site_part = text.split("-", 1)
                    # pulizia nome
                    name = re.sub(r"^[\s\*\d\.\)\-]+", "", name_part)
                    name = re.sub(r"\*\*", "", name).strip()

                    # estrazione URL Markdown, fallback a testo grezzo
                    md_link = re.compile(r'\[.*?\]\(\s*(https?://[^\)]+)\s*\)')
                    m = md_link.search(site_part)
                    raw = m.group(1) if m else site_part.strip()
                    raw = re.sub(r'^[\*\s]+', '', raw)  # rimuovo bullet residui

                    # normalizzo schema
                    if re.match(r'^[a-zA-Z0-9\-.]+\.[a-z]{2,}', raw):
                        site = "https://" + raw
                    elif raw.startswith("http"):
                        site = raw
                    else:
                        site = None
                else:
                    name = line.strip()
                    site = find_site_by_name(name)
                if name not in found_names and site:
                    companies.append((name, site))
                    found_names.add(name)
                if len(companies) >= 10:
                    break
            log(f"🌐 Trovate {len(companies)} aziende dal modello")

            def process_company(name, url):
                domain = urlparse(url).netloc
                with lock:
                    if any(d["Sito Web"] == domain for d in data_utili):
                        log(f"⚠️ Dominio già processato: {domain}")
                        return
                emails, status = extract_emails_from_url(url)
                result = {
                    "Nome Azienda": name,
                    "Sito Web": domain,
                    "Email trovate": ", ".join(emails) if emails else "Nessuna",
                    "Stato": status
                }
                with lock:
                    if emails:
                        data_utili.append(result)
                        log(f"✅ Email trovate per {name}: {result['Email trovate']}")
                    else:
                        data_scartati.append(result)
                        log(f"❌ Nessuna email per {name}")

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(process_company, name, site) for name, site in companies]
                for f in futures:
                    f.result()
                    progress_bar.progress(min(1.0, len(data_utili) / max_results))

                # Mostra i log dopo l'elaborazione del batch
                with log_lock:
                    if debug_lines:
                        st.markdown("🪵 **Log Debug:**")
                        st.markdown("\n".join(f"- {line}" for line in debug_lines[-25:]))
                        debug_lines.clear()

            if not any(d["Email trovate"] != "Nessuna" for d in data_utili[-len(companies):]):
                log("⚠️ Nessuna email valida trovata in questo batch. Interrompo il ciclo.")
                break

        st.session_state.data_utili = data_utili
        st.session_state.data_scartati = data_scartati

        with st.expander("🪵 Log dettagliato (debug)"):
            for line in debug_lines:
                st.markdown(f"- {line}")

    if st.session_state.data_utili:
        #Sezione tabella risultati positivi
        st.success("✅ Risultati Utilizzabili")

        selected_email_idx = st.session_state.get("selected_email_idx", None)
        for idx, entry in enumerate(st.session_state.data_utili):
            with st.form(key=f"company_form_{idx}", clear_on_submit=False):
                col1, col2, col3, col4, col5 = st.columns([2, 3, 3, 3, 2])
                with col1:
                    st.markdown(f"**{entry['Nome Azienda']}**")
                with col2:
                    st.markdown(entry["Sito Web"])
                with col3:
                    st.markdown(entry["Email trovate"])
                with col4:
                    st.markdown(entry["Stato"])
                with col5:
                    if st.form_submit_button("✉️ Scrivi Email"):
                        st.session_state.selected_email_idx = idx
                        st.session_state.email_json_data = pd.DataFrame([entry]).to_json(orient="records", indent=2,
                                                                                         force_ascii=False)
                        st.rerun()

            # Se è selezionata questa azienda, mostra il form email
            if selected_email_idx == idx:
                st.markdown("#### ✍️ Componi Email")
                show_email_interface(st.session_state.email_json_data)

                # Aggiungi pulsante per chiudere il modulo email
                if st.button("❌ Chiudi modulo email", key=f"close_email_{idx}"):
                    st.session_state.selected_email_idx = None
                    st.rerun()

        #sezione scaricare tutti i contatti in json.
        df = pd.DataFrame(st.session_state.data_utili)
        #st.dataframe(df, use_container_width=True) è la tabella originale.
        json_results = df.to_json(orient="records", indent=2, force_ascii=False)
        st.download_button("📥 Scarica risultati in JSON", json_results, "risultati.json", "application/json")

    #sezione tabella scarti
    if st.session_state.data_scartati:
        st.markdown("---")
        st.error("⚠️ Risultati Scartati")
        st.dataframe(pd.DataFrame(st.session_state.data_scartati), use_container_width=True)


def main():
    st.sidebar.title("📚 Navigazione")

    # Se la sessione è pronta per passare direttamente all'email
    if st.session_state.start_email_flow and st.session_state.email_json_data:
        st.sidebar.radio("Seleziona sezione", ["Ricerca Email", "Invio Email"], index=1, key="section_choice")
        show_email_interface(st.session_state.email_json_data)
        return

    section = st.sidebar.radio("Seleziona sezione", ["Ricerca Email", "Invio Email"], key="section_choice")

    if section == "Ricerca Email":
        show_scraper_interface()
    elif section == "Invio Email":
        show_email_interface()


if __name__ == "__main__":
    main()