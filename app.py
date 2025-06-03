# app.py (l'app Streamlit principale)
import streamlit as st
import pandas as pd
from urllib.parse import urlparse, urljoin
import cloudscraper
from bs4 import BeautifulSoup
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import requests # Importa requests
import json # Importa json

from utils import clean_valid_emails, EMAIL_CANDIDATE_REGEX, PRIORITY_KEYWORDS
# Assicurati che utils_llm.py sia corretto e non contenga chiavi API hardcoded
from utils_llm import call_gemini_flash
from email_ui import show_email_interface
from googlesearch import search
from tracking_ui import EmailTrackerUI

st.set_page_config(page_title="Trova Clienti", layout="wide")

# URL del server Flask deployato su PythonAnywhere
FLASK_SERVER_BASE_URL = "https://marzoli95.pythonanywhere.com"

PARTITA_IVA_REGEX = r"\b(IT)?\s?\d{11}\b"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

try:
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
except Exception as e:
    st.error(f"Errore durante l'inizializzazione di cloudscraper: {e}")
    scraper = None

# Inizializzazione stati di sessione all'inizio dello script
if "data_utili" not in st.session_state: st.session_state.data_utili = []
if "data_scartati" not in st.session_state: st.session_state.data_scartati = []
if "start_email_flow" not in st.session_state: st.session_state.start_email_flow = False
if "email_json_data" not in st.session_state: st.session_state.email_json_data = None
if "main_search_triggered" not in st.session_state: st.session_state.main_search_triggered = False
if "selected_email_idx" not in st.session_state: st.session_state.selected_email_idx = None
if 'ui_visible_log_messages' not in st.session_state: st.session_state.ui_visible_log_messages = []
if 'selected_llm_models' not in st.session_state: st.session_state.selected_llm_models = ["Gemini_Flash_2_0"]

# Nuovo stato di sessione per l'utente autenticato
if 'authenticated_user_email' not in st.session_state:
    st.session_state.authenticated_user_email = None

# --- Gestione del callback OAuth ---
query_params = st.query_params
if query_params:
    if "auth_status" in query_params:
        if query_params["auth_status"] == "success":
            st.session_state.authenticated_user_email = query_params.get("user_email")
            st.success(f"✅ Autenticazione Gmail riuscita per: {st.session_state.authenticated_user_email}")
            # Pulisci i query params per evitare di ri-autenticare al refresh
            st.query_params.clear() # Rimuovi i parametri dalla URL
            st.rerun() # Ricarica per pulire l'URL
        elif query_params["auth_status"] == "failure":
            error_message = query_params.get("error", "Errore sconosciuto.")
            st.error(f"❌ Autenticazione Gmail fallita: {error_message}")
            st.query_params.clear()
            st.rerun()

# --- Funzioni Helper per lo Scraping (invariate dalla tua ultima versione funzionante) ---
# ... (le tue funzioni get_with_retries, extract_emails_and_piva, try_common_contact_pages, extract_emails_from_url, generate_company_list_prompt, find_site_by_name) ...
def get_with_retries(url, unhealthy_domains_set, max_retries=2, timeout=8, backoff_factor=0.3):
    if not scraper: raise Exception("Scraper non inizializzato.")
    try:
        current_netloc = urlparse(url).netloc
        if current_netloc in unhealthy_domains_set:
            raise Exception(f"Dominio {current_netloc} blacklistato.")
    except Exception as e_parse_url:
        raise Exception(f"URL malformato: {url} - {e_parse_url}")

    for attempt in range(max_retries):
        try:
            response = scraper.get(url, timeout=timeout, headers=HEADERS, allow_redirects=True)
            response.raise_for_status()
            return response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects) as e:
            if attempt == max_retries - 1:
                unhealthy_domains_set.add(current_netloc)
                raise Exception(f"Max retries {url}. Err:{type(e).__name__}") from e
            time.sleep(backoff_factor * (2 ** attempt))
        except requests.exceptions.HTTPError as eHttp:  # Rinominata per evitare conflitto con la 'e' esterna
            if eHttp.response.status_code in [500, 502, 503, 504]:
                if attempt == max_retries - 1: unhealthy_domains_set.add(current_netloc); raise
                time.sleep(backoff_factor * (2 ** attempt));
                continue
            raise
        except Exception as eGeneral:  # Rinominata per evitare conflitto
            if attempt == max_retries - 1:
                if "resolve" in str(eGeneral).lower() or "socket" in str(eGeneral).lower() or "connection" in str(
                        eGeneral).lower():
                    unhealthy_domains_set.add(current_netloc)
                raise
            time.sleep(backoff_factor * (2 ** attempt))
    return None


def extract_emails_and_piva(html_text, url_context=""):
    soup = BeautifulSoup(html_text, "html.parser")
    mailtos = []
    try:
        mailtos = [a.get("href")[7:] for a in soup.find_all("a", href=True) if a.get("href", "").startswith("mailto:")]
    except Exception:
        pass
    text_content = soup.get_text();
    text_content = "" if text_content is None else text_content.lower()
    text_emails = re.findall(EMAIL_CANDIDATE_REGEX, text_content)
    partita_iva_match = re.search(PARTITA_IVA_REGEX, text_content)
    if not partita_iva_match: partita_iva_match = re.search(PARTITA_IVA_REGEX, html_text)
    header_emails, footer_emails = [], []
    header = soup.find("header")
    if header and header.get_text(): header_emails = re.findall(EMAIL_CANDIDATE_REGEX, header.get_text().lower())
    footer = soup.find("footer")
    if footer and footer.get_text(): footer_emails = re.findall(EMAIL_CANDIDATE_REGEX, footer.get_text().lower())
    all_emails = list(set(mailtos + text_emails + header_emails + footer_emails))
    filtered_emails = clean_valid_emails(all_emails)
    filtered_emails.sort(key=lambda e: (not any(k in e for k in PRIORITY_KEYWORDS), e))
    return filtered_emails[:3], bool(partita_iva_match)


def try_common_contact_pages(base_url, unhealthy_domains_set):
    contact_paths = ["/contatti", "/contact", "/chi-siamo", "/about", "/legal", "/privacy"]
    found_emails_set, statuses, found_piva_overall = set(), [], False
    try:
        parsed_base = urlparse(base_url);
        scheme = parsed_base.scheme or "https";
        netloc = parsed_base.netloc or parsed_base.path.split('/')[0]
        if not netloc: statuses.append(f"URL base non valido: {base_url}"); return [], False, statuses
        if netloc in unhealthy_domains_set: statuses.append(
            f"Dominio base {netloc} blacklistato."); return [], False, statuses
    except Exception as e:
        statuses.append(f"Errore parsing URL {base_url}: {e}");
        return [], False, statuses
    base_url_proper = f"{scheme}://{netloc.rstrip('/')}"
    for path in contact_paths:
        contact_url = urljoin(base_url_proper, path)
        try:
            resp = get_with_retries(contact_url, unhealthy_domains_set)
            if resp and resp.status_code == 200:
                emails_page, has_piva_page = extract_emails_and_piva(resp.text, contact_url)
                found_emails_set.update(emails_page)
                if has_piva_page: found_piva_overall = True
                statuses.append(f"{path}:ok(E:{len(emails_page)},P:{'S' if has_piva_page else 'N'})")
            elif resp:
                statuses.append(f"{path}:{resp.status_code}")
        except Exception as ePage:  # Rinominata per evitare conflitto
            statuses.append(f"{path}:err({type(ePage).__name__})")
    return list(found_emails_set), found_piva_overall, statuses


def extract_emails_from_url(url, unhealthy_domains_set):
    emails_home, piva_home, final_emails_list, overall_piva_found = [], False, [], False
    status_home, contact_statuses_str = "Non tentato", "Non tentato"
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme: url = "https://" + url
        if parsed_url.netloc in unhealthy_domains_set: raise Exception(f"Dominio {parsed_url.netloc} blacklistato.")
        response_home = get_with_retries(url, unhealthy_domains_set)
        if response_home and response_home.status_code == 200:
            emails_home, piva_home = extract_emails_and_piva(response_home.text, url)
            status_home = f"H:ok(E:{len(emails_home)},P:{'S' if piva_home else 'N'})"
        elif response_home:
            status_home = f"H:{response_home.status_code}"
        emails_contact_list, piva_contact_pages, contact_statuses = try_common_contact_pages(url, unhealthy_domains_set)
        contact_statuses_str = (', '.join(contact_statuses[:2]) + (
            '...' if len(contact_statuses) > 2 else '')) if contact_statuses else "N/A"
        all_found_emails = list(set(emails_home + emails_contact_list))
        cleaned_emails = clean_valid_emails(all_found_emails)
        cleaned_emails.sort(key=lambda e: (not any(k in e for k in PRIORITY_KEYWORDS), e))
        final_emails_list, overall_piva_found = cleaned_emails[:3], piva_home or piva_contact_pages
    except Exception as e:  # Variabile 'e' generica per l'eccezione principale della funzione
        status_home = f"H:Err({type(e).__name__})"  # Non mostra l'intero errore per brevità

    s_list = []  # Rinominata da 's' per evitare confusione con la 's' usata come nome variabile per stringhe altrove
    if final_emails_list: s_list.append("E")
    if overall_piva_found: s_list.append("P")
    found_str = "&".join(s_list) if s_list else "Nulla"
    final_status = f"{found_str}. {status_home}. C:{contact_statuses_str}"
    return final_emails_list, overall_piva_found, final_status.strip()


def generate_company_list_prompt(settore, regione, dimensione, exclude_names, num_results):
    exclude_str = ", ".join(exclude_names) if exclude_names else "nessuno"
    return (
        f"Elenca {num_results} piccole aziende italiane di {settore.lower()}, <{dimensione} dipendenti, in {regione}. Includi sito web (formato: www.esempio.it o https://www.esempio.it). Evita questi nomi: {exclude_str}.\nFormato: Nome - Sito\nEsempio:\nABC Formazione - www.abcformazione.it")


def find_site_by_name(name, log_func_thread_safe):  # log_func_thread_safe è corretto
    try:
        query = f"{name} sito ufficiale";
        log_func_thread_safe(f"Google: '{query}'")
        for url in search(query, num_results=3, lang="it", sleep_interval=1, timeout=5):
            log_func_thread_safe(f"Google res: {url}")
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"] or any(
                    sd_domain in parsed.netloc.lower() for sd_domain in  # Rinominata variabile sd
                    ["facebook.com", "linkedin.com", "instagram.com",
                     "twitter.com", "google.com", "paginegialle.it"]): continue
            if '#' in parsed.path or ('.' in parsed.path.split('/')[-1] and not any(
                    parsed.path.endswith(html_ext) for html_ext in
                    ['.html', '.htm', '.php'])):  # Rinominata variabile ext
                if not (parsed.path == '/' or parsed.path == ''): continue
            if "." in parsed.netloc.lower() and len(parsed.netloc.split('.')) <= 4 and len(
                    parsed.netloc.split('.')[-1]) >= 2: return url
    except Exception as e:  # Variabile 'e' generica per l'eccezione principale della funzione
        log_func_thread_safe(f"Err Google '{name}': {e}")
    return None

# Dizionario dei modelli LLM disponibili
LLM_MODELS = {
    "Gemini_Flash_2_0": call_gemini_flash,
    # Aggiungi qui altri modelli LLM se ne hai (es. "OpenAI GPT-3.5": call_openai_gpt35)
    # Esempio: "Altro Modello": another_llm_function,
}

def show_scraper_interface():
    st.title("🚀 Trova Clienti Superveloce")

    thread_log_lines = []
    thread_log_lock = threading.Lock()
    log_expander = st.expander("🪵 Log di Debug", expanded=False)
    log_container = log_expander.empty()

    if 'ui_visible_log_messages' not in st.session_state: st.session_state.ui_visible_log_messages = []

    def main_thread_ui_logger(message):
        timestamped_message = f"- {time.strftime('%H:%M:%S')}(UI): {message}"
        with thread_log_lock:
            if thread_log_lines: st.session_state.ui_visible_log_messages.extend(
                thread_log_lines); thread_log_lines.clear()
        st.session_state.ui_visible_log_messages.append(timestamped_message)
        log_container.markdown("\n".join(st.session_state.ui_visible_log_messages[-75:]), unsafe_allow_html=True)
        print(timestamped_message)

    def thread_safe_log(message):
        timestamped_message = f"- {time.strftime('%H:%M:%S')}(THR): {message}"
        with thread_log_lock: thread_log_lines.append(timestamped_message)
        print(timestamped_message)

    with st.form(key="filtro_form"):
        c1, c2 = st.columns(2)
        with c1:
            settore = st.text_input("Settore", value=st.session_state.get("settore_input", "IA"),
                                    key="settore_input_widget")
            regione = st.text_input("Regione", value=st.session_state.get("regione_input", "Marche"),
                                    key="regione_input_widget")
        with c2:
            dimensione = st.number_input("Max Dipendenti", 1, 1000, st.session_state.get("dimensione_input", 20), 1,
                                         key="dimensione_input_widget")
            max_results = st.slider("Risultati Desiderati", 5, 100, st.session_state.get("max_results_input", 10),
                                    key="max_results_input_widget")

        selected_llm_models = st.multiselect(
            "Seleziona modelli LLM da usare",
            list(LLM_MODELS.keys()),
            default=st.session_state.get("selected_llm_models", ["Gemini_Flash_2_0"]),
            key="llm_models_selector"
        )
        st.session_state.selected_llm_models = selected_llm_models

        main_search_button_clicked = st.form_submit_button("⚡ Cerca Clienti Ora!")

    if main_search_button_clicked:
        st.session_state.settore_input = settore
        st.session_state.regione_input = regione
        st.session_state.dimensione_input = dimensione
        st.session_state.max_results_input = max_results
        st.session_state.main_search_triggered = True
        st.session_state.selected_email_idx = None
        st.session_state.email_json_data = None
        st.rerun()

    if st.session_state.get("main_search_triggered", False):
        st.session_state.main_search_triggered = False

        if not scraper: st.error("Cloudscraper non inizializado."); return

        st.session_state.data_utili = []
        st.session_state.data_scartati = []
        st.session_state.ui_visible_log_messages = []
        with thread_log_lock:
            thread_log_lines.clear()

        unhealthy_domains_for_run = set()
        main_thread_ui_logger(f"Avvio ricerca: {st.session_state.settore_input}, {st.session_state.regione_input}...")
        if not st.session_state.selected_llm_models:
            st.warning("Nessun modello LLM selezionato. Selezionane almeno uno per avviare la ricerca.")
            return

        processed_identifiers = set()
        progress_bar_placeholder = st.empty()
        status_placeholder = st.empty()
        max_llm_iterations, llm_iteration, no_new_company_batches = 15, 0, 0

        while len(
                st.session_state.data_utili) < st.session_state.max_results_input and llm_iteration < max_llm_iterations:
            llm_iteration += 1
            status_placeholder.info(
                f"⏳ LLM {llm_iteration}/{max_llm_iterations}. Utili: {len(st.session_state.data_utili)}/{st.session_state.max_results_input}")

            excluded_names = {name for name, _ in processed_identifiers}
            prompt = generate_company_list_prompt(st.session_state.settore_input, st.session_state.regione_input,
                                                  st.session_state.dimensione_input, list(excluded_names),
                                                  st.session_state.max_results_input)

            combined_llm_output = ""
            for model_name in st.session_state.selected_llm_models:
                llm_function = LLM_MODELS.get(model_name)
                if llm_function:
                    try:
                        output_llm = llm_function(prompt)
                        main_thread_ui_logger(
                            f"Debug LLM '{model_name}': Output ricevuto. Lunghezza: {len(output_llm) if output_llm else 0} caratteri.")
                        combined_llm_output += (output_llm if output_llm else "") + "\n"
                    except Exception as e:
                        main_thread_ui_logger(f"⛔ Errore LLM '{model_name}': {e}.")
                else:
                    main_thread_ui_logger(f"⚠️ Modello LLM '{model_name}' non trovato o non implementato.")


            if not combined_llm_output.strip(): main_thread_ui_logger("⚠️ Output combinato LLM vuoto."); time.sleep(0.5); continue

            companies_from_llm = []
            for line in combined_llm_output.strip().splitlines():
                line = line.strip();
                name, site_str = None, None
                if not line or line.startswith(
                        "---") or "<Nome Azienda>" in line or "```" in line or "elenco" in line.lower(): continue
                m_md = re.match(r'\*?\s*(.+?)\s*-\s*\[.*?\]\((https?://[^\)]+)\)', line);
                m_s = re.match(r'\*?\s*(.+?)\s*-\s*(https?://.+)', line);
                m_sw = re.match(r'\*?\s*(.+?)\s*-\s*(www\..+)', line)
                match_md_corrected = re.match(r'\*?\s*(.+?)\s*-\s*\[.*?\]\((https?://[^\)]+)\)', line)
                if match_md_corrected:
                    name, site_str = match_md_corrected.group(1).strip(), match_md_corrected.group(2).strip()
                elif m_s:
                    name, site_str = m_s.group(1).strip(), m_s.group(2).strip()
                elif m_sw:
                    name, site_str = m_sw.group(1).strip(), "https://" + m_sw.group(2).strip()
                elif "-" in line:
                    parts = line.split("-", 1);
                    name = parts[0].replace("*", "").strip();
                    raw_site = parts[1].strip()
                    if re.match(r'^(https?://)?(www\.)?[a-zA-Z0-9\-.]+\.[a-z]{2,}', raw_site,
                                re.I): site_str = "https://" + raw_site if not raw_site.startswith(
                        ("http", "https")) else raw_site
                else:
                    name = line.replace("*", "").strip()

                if name and not site_str: site_str = find_site_by_name(name, thread_safe_log)

                if name and site_str:
                    try:
                        domain = urlparse(site_str).netloc.lower().replace("www.", "")
                        if not domain: continue
                        identifier = (name.lower(), domain)
                        if identifier not in processed_identifiers: companies_from_llm.append(
                            (name, site_str)); processed_identifiers.add(identifier)
                    except Exception:
                        pass
                if len(companies_from_llm) >= st.session_state.max_results_input + 5: break # Un po' di margine per il parsing

            if not companies_from_llm:
                no_new_company_batches += 1
            else:
                no_new_company_batches = 0
            if no_new_company_batches >= 3: main_thread_ui_logger("⚠️ Stallo LLM."); break
            if not companies_from_llm: time.sleep(0.5); continue

            batch_utili, batch_scartati = [], []

            def process_company_thread(name_c, url_c, log_f, unh_set):
                emails, p_iva, status = extract_emails_from_url(url_c, unh_set)
                useful = bool(emails)
                res = {"Nome Azienda": name_c, "Sito Web": urlparse(url_c).netloc.lower().replace("www.", ""),
                       "Email trovate": ", ".join(emails) if emails else "Nessuna",
                       "P.IVA Trovata": "Sì" if p_iva else "No", "Stato": status}
                return res, useful

            with ThreadPoolExecutor(max_workers=8) as executor:
                f_to_co = {
                    executor.submit(process_company_thread, n, s, thread_safe_log, unhealthy_domains_for_run): (n, s)
                    for n, s in companies_from_llm}
                for f in f_to_co:
                    n_orig, u_orig = f_to_co[f]
                    try:
                        r_res, was_u = f.result()
                    except Exception as e_thr:
                        main_thread_ui_logger(f"⛔ Errore thr {n_orig}: {e_thr}");
                        r_res = {"Nome Azienda": n_orig,
                                 "Sito Web": urlparse(
                                     u_orig).netloc.lower().replace(
                                     "www.", ""),
                                 "Email trovate": "ERR",
                                 "P.IVA Trovata": "ERR",
                                 "Stato": f"Exc: {type(e_thr).__name__}"};
                        was_u = False
                    if r_res: (batch_utili if was_u else batch_scartati).append(r_res)

            if batch_utili: st.session_state.data_utili.extend(batch_utili)
            if batch_scartati: st.session_state.data_scartati.extend(batch_scartati)

            prog = min(1.0,
                       len(st.session_state.data_utili) / st.session_state.max_results_input if st.session_state.max_results_input > 0 else 0)
            progress_bar_placeholder.progress(prog)
            main_thread_ui_logger(
                f"Batch: Utili {len(batch_utili)}, Scarti {len(batch_scartati)}. Blacklist: {len(unhealthy_domains_for_run)}")

        status_placeholder.success(
            f"🏁 Ricerca terminata! Utili:{len(st.session_state.data_utili)}, Scarti:{len(st.session_state.data_scartati)}")
        progress_bar_placeholder.empty()
        main_thread_ui_logger(
            f"Fine. Blacklist: {list(unhealthy_domains_for_run) if unhealthy_domains_for_run else 'No'}.")
        with thread_log_lock:
            if thread_log_lines: st.session_state.ui_visible_log_messages.extend(
                thread_log_lines); thread_log_lines.clear()
        if 'ui_visible_log_messages' in st.session_state: log_container.markdown(
            "\n".join(st.session_state.ui_visible_log_messages[-75:]), unsafe_allow_html=True)

    if st.session_state.data_utili:
        st.success(f"✅ Risultati Utilizzabili ({len(st.session_state.data_utili)})")

        df_utili_display = pd.DataFrame(st.session_state.data_utili)
        if not df_utili_display.empty:
            df_utili_display = df_utili_display[["Nome Azienda", "Sito Web", "Email trovate", "P.IVA Trovata", "Stato"]]

        for idx, entry in enumerate(st.session_state.data_utili):
            col1, col2, col3, col4, col5 = st.columns([2, 3, 3, 2, 2])
            with col1:
                st.markdown(f"**{entry['Nome Azienda']}**")
            with col2:
                site_domain = entry["Sito Web"]
                if site_domain and site_domain not in ["N/A", "ERR", "ERRORE"]:
                    link_url = f"https://{site_domain}"
                    st.markdown(f"[{site_domain}]({link_url})")
                else:
                    st.markdown(site_domain)
            with col3:
                st.markdown(entry["Email trovate"])
            with col4:
                st.markdown(f"P.IVA: {entry['P.IVA Trovata']}")
            with col5:
                if st.button("✉️ Scrivi", key=f"scrivi_email_btn_{idx}"):
                    st.session_state.selected_email_idx = idx
                    email_data = {k: entry.get(k) for k in
                                  ["Nome Azienda", "Sito Web", "Email trovate", "P.IVA Trovata"]}
                    st.session_state.email_json_data = pd.DataFrame([email_data]).to_json(orient="records", indent=2,
                                                                                          force_ascii=False)
                    st.rerun()

            if st.session_state.selected_email_idx == idx and st.session_state.email_json_data:
                st.markdown("---")
                st.markdown("#### ✍️ Componi Email")
                show_email_interface(st.session_state.email_json_data)
                if st.button("❌ Chiudi Modulo", key=f"close_email_form_btn_{idx}"):
                    st.session_state.selected_email_idx = None
                    st.session_state.email_json_data = None
                    st.rerun()
                st.markdown("---")

        if not df_utili_display.empty:
            json_utili = df_utili_display.to_json(orient="records", indent=2, force_ascii=False)
            st.download_button("📥 Utili (JSON)", json_utili,
                               f"clienti_utili_{st.session_state.get('settore_input', 'na')}_{st.session_state.get('regione_input', 'na')}.json",
                               "application/json")

    if st.session_state.data_scartati:
        st.markdown("---")
        st.error(f"⚠️ Risultati Scartati ({len(st.session_state.data_scartati)})")
        df_scartati_display = pd.DataFrame(st.session_state.data_scartati)
        if not df_scartati_display.empty:
            cols_scarti = ["Nome Azienda", "Sito Web", "Email trovate", "P.IVA Trovata", "Stato"]
            df_scartati_display = df_scartati_display[
                [col for col in cols_scarti if col in df_scartati_display.columns]]
            st.dataframe(df_scartati_display, use_container_width=True, height=200)
            json_scarti = df_scartati_display.to_json(orient="records", indent=2, force_ascii=False)
            st.download_button("📥 Scarti (JSON)", json_scarti,
                               f"clienti_scartati_{st.session_state.get('settore_input', 'na')}_{st.session_state.get('regione_input', 'na')}.json",
                               "application/json")

def main():
    st.sidebar.title("📚 Navigazione")
    if 'main_section_choice' not in st.session_state:
        st.session_state.main_section_choice = "Ricerca Email"

    # --- LOGIN/LOGOUT Gmail ---
    if st.session_state.authenticated_user_email:
        st.sidebar.success(f"Connesso come: {st.session_state.authenticated_user_email}")
        if st.sidebar.button("Logout Gmail"):
            st.session_state.authenticated_user_email = None
            st.info("Disconnesso da Gmail.")
            st.rerun()
    else:
        st.sidebar.warning("Non connesso a Gmail.")
        # Link al server Flask per avviare il flusso OAuth
        oauth_url = f"{FLASK_SERVER_BASE_URL}/authorize_gmail"
        st.sidebar.markdown(f"[Login con Gmail]({oauth_url})", unsafe_allow_html=True)
        st.sidebar.info("Clicca per autorizzare l'applicazione a inviare email dal tuo account Gmail.")

    section = st.sidebar.radio(
        "Seleziona sezione",
        ["Ricerca Email", "Invio Email", "Tracciamento Email"],
        key="main_section_choice",
        horizontal=True
    )

    if section == "Ricerca Email":
        show_scraper_interface()
    elif section == "Invio Email":
        if st.session_state.authenticated_user_email:
            st.subheader("Modulo Invio Email Globale")
            show_email_interface(st.session_state.get("email_json_data", None))
        else:
            st.warning("Per inviare email, devi prima autenticarti con il tuo account Gmail.")
    elif section == "Tracciamento Email":
        email_tracker_ui = EmailTrackerUI()
        email_tracker_ui.show_interface()

    # --- LOGICA DI AUTO-REFRESH GLOBALE ---
    if section == "Tracciamento Email":
        time.sleep(3)  # Attende 3 secondi prima di ri-eseguire lo script
        st.rerun()  # Forza il ricaricamento dell'intera app Streamlit


if __name__ == "__main__":
    main()