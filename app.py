import streamlit as st
import pandas as pd
from urllib.parse import urlparse
from duckduckgo_search import DDGS
import cloudscraper
from bs4 import BeautifulSoup
import re
from llama_cpp import Llama
import threading
from concurrent.futures import ThreadPoolExecutor
from email_validator import validate_email, EmailNotValidError
from googlesearch import search
from email_sender import EmailSender


# Impostazioni per Streamlit
st.set_page_config(page_title="Trova Clienti", layout="wide")

# Regex per trovare email candidate (filtrate poi con validazione)
EMAIL_CANDIDATE_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Crea il scraper per l'analisi dei siti
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False},
    disableCloudflareV1=True
)

# Lazy loading per il modello LLM
_llm = None
def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(model_path="models/mistral-7b-instruct-v0.1.Q4_K_M.gguf", n_ctx=2048, n_threads=4)
    return _llm

# Funzione per cercare su Google.
def google_search_sites(query, max_results):
    results = []
    seen_domains = set()
    try:
        for url in search(query, num_results=max_results):
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain not in seen_domains:
                seen_domains.add(domain)
                results.append(url)
            if len(results) >= max_results:
                break
    except Exception as e:
        print(f"Errore nella ricerca Google: {e}")
    return results

# Funzione per cercare su DuckDuckGo
def duckduckgo_search_sites(query, max_results):
    results = []
    seen_domains = set()
    with DDGS() as ddgs:
        try:
            for r in ddgs.text(query, max_results=max_results):
                url = r.get("url") or r.get("href")
                if url and url.startswith("http"):
                    parsed = urlparse(url)
                    domain = parsed.netloc
                    if domain not in seen_domains:
                        seen_domains.add(domain)
                        results.append(url)
                if len(results) >= max_results:
                    break
        except Exception as e:
            print(f"Errore nella ricerca DuckDuckGo: {e}")
    return results

# Funzione per estrarre email con priorità
PRIORITY_KEYWORDS = ["hr", "risorse", "human", "info", "lavoro"]

def clean_valid_emails(emails):
    valid_emails = []
    for e in emails:
        try:
            valid = validate_email(e, check_deliverability=False)
            email = valid.email
            if not email.startswith(tuple("0123456789")) and email.split("@")[ -1].split(".")[-1] in ["com","it","gov","net","org","info","edu","mil","ru","cn","uk","io","int","mobi","biz","fr","de","xyz","sale","career"]:
                valid_emails.append(email)
        except EmailNotValidError:
            continue
    return list(set(valid_emails))

def extract_clean_emails(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    mailtos = [a.get("href")[7:] for a in soup.find_all("a", href=True) if a.get("href", "").startswith("mailto:")]
    text_emails = re.findall(EMAIL_CANDIDATE_REGEX, soup.get_text().lower())
    header = soup.find("header")
    footer = soup.find("footer")
    header_emails = re.findall(EMAIL_CANDIDATE_REGEX, header.get_text().lower()) if header else []
    footer_emails = re.findall(EMAIL_CANDIDATE_REGEX, footer.get_text().lower()) if footer else []
    all_emails = list(set(mailtos + text_emails + header_emails + footer_emails))

    filtered = clean_valid_emails(all_emails)
    filtered.sort(key=lambda e: (not any(k in e for k in PRIORITY_KEYWORDS), e))

    return filtered[:3]

def try_common_contact_pages(base_url):
    contact_paths = ["/contatti", "/contact", "/about", "/chi-siamo", "/contact-us/"]
    found_emails = []
    statuses = []

    for path in contact_paths:
        contact_url = base_url.rstrip("/") + path
        try:
            resp = scraper.get(contact_url, timeout=10)
            if resp.status_code == 200:
                emails = extract_clean_emails(resp.text)
                found_emails += emails
                statuses.append(f"{path}: ok")
            else:
                statuses.append(f"{path}: {resp.status_code} - {resp.reason}")
        except Exception as e:
            statuses.append(f"{path}: errore - {str(e)}")

    return list(set(found_emails)), statuses

def extract_emails_from_url(url):
    try:
        response = scraper.get(url, timeout=10, headers=HEADERS, allow_redirects=True)
        if response.status_code != 200:
            return [], f"Errore HTTP {response.status_code} - {response.reason} ({url})"

        base_emails = extract_clean_emails(response.text)
        if base_emails:
            return base_emails, "Email trovate nella pagina principale"

        contact_emails, contact_statuses = try_common_contact_pages(url)
        if contact_emails:
            return contact_emails, "Email trovate in pagine di contatto"

        return [], f"Nessuna email trovata ({', '.join(contact_statuses)})"

    except Exception as e:
        return [], f"Errore durante l'accesso a {url}: {str(e)}"


def main():
    st.title("🔍 Ricerca Clienti Aziendali + Email")
    st.markdown("Compila il form qui sotto per cercare aziende e trovare i loro contatti email.")

    # Carica o inizializza i dati in sessione
    if "data_utili" not in st.session_state:
        st.session_state.data_utili = []
    if "data_scartati" not in st.session_state:
        st.session_state.data_scartati = []

    with st.form(key="filtro_form"):
        settore = st.selectbox("Settore", ["", "Realtà aumentata", "Risorse Umane", "Informatica", "Marketing", "Finanza"])
        regione = st.selectbox("Regione", [
            "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia-Romagna", "Friuli Venezia Giulia",
            "Lazio", "Liguria", "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna", "Sicilia",
            "Toscana", "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto"])
        dimensione = st.selectbox("Dimensione Aziendale", ["", "Piccola", "Media", "Grande"])
        codice_ateco = st.selectbox("Codice ATECO", ["", "62.01", "63.11", "72.10", "73.11", "74.10", "74.90", "80.10", "82.99"])
        max_results = st.slider("Numero di risultati positivi da restituire", 1, 100, 50)
        search_engine = st.radio("Motore di Ricerca", ("DuckDuckGo", "Google"))
        submitted = st.form_submit_button("Cerca Clienti")

    if submitted:
        llm = get_llm()
        visited_domains = set()
        used_queries = set()
        data_utili = []
        data_scartati = []
        lock = threading.Lock()
        max_attempts = 10
        progress_bar = st.progress(0)
        attempts = 0

        st.info("⏳ Ricerca in corso... questo potrebbe richiedere un po' di tempo.")

        while len(data_utili) < max_results and attempts < max_attempts:
            attempts += 1

            with st.spinner(f"Generazione query intelligente (tentativo {attempts})..."):
                prompt = (
                    f"You are a marketing expert. Generate a single varied search query in Italian that can be used on '{search_engine}' to find Italian companies in the '{settore}' sector, "
                    f"located in '{regione}', with a size of '{dimensione}', ATECO code '{codice_ateco}'. The query must be original and different from previously generated ones. "
                    "Return only the query in Italian, without quotes or explanations."
                )
                output = llm(prompt=f"[INST] {prompt} [/INST]", max_tokens=100, temperature=0.9, stop=["</s>"])
                query = output["choices"][0]["text"].strip()

                if query in used_queries:
                    continue
                used_queries.add(query)
                st.info(f"Query generata: {query}")

            all_urls = google_search_sites(query, max_results=max_results * 10) if search_engine == "Google" else duckduckgo_search_sites(query, max_results=max_results * 10)

            def process_url(i, url):
                domain = urlparse(url).netloc
                with lock:
                    if domain in visited_domains or len(data_utili) >= max_results:
                        return
                    visited_domains.add(domain)

                emails, status = extract_emails_from_url(url)
                result = {
                    "Sito Web": domain,
                    "Email trovate": ", ".join(emails) if emails else "Nessuna",
                    "Stato": status
                }

                with lock:
                    if emails and len(data_utili) < max_results:
                        data_utili.append(result)
                    else:
                        data_scartati.append(result)

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i, url in enumerate(all_urls):
                    if len(data_utili) >= max_results:
                        break
                    futures.append(executor.submit(process_url, i, url))
                for i, future in enumerate(futures):
                    future.result()
                    progress_bar.progress(min(1.0, len(data_utili) / max_results))

        st.session_state.data_utili = data_utili
        st.session_state.data_scartati = data_scartati

    # Mostra risultati anche dopo il submit o dopo un download
    if st.session_state.data_utili:
        st.success("✅ Risultati Utilizzabili")
        df_validi = pd.DataFrame(st.session_state.data_utili)
        st.dataframe(df_validi, use_container_width=True)
        json_results = df_validi.to_json(orient="records", indent=2, force_ascii=False)
        st.download_button("📥 Scarica risultati in JSON", json_results, "risultati.json", "application/json")

    if st.session_state.data_scartati:
        st.markdown("---")
        st.error("⚠️ Risultati Scartati")
        df_scartati = pd.DataFrame(st.session_state.data_scartati)
        st.dataframe(df_scartati, use_container_width=True)

    # Sezione email
    st.markdown("---")
    st.header("📧 Invia Email ai Contatti Trovati")
    uploaded_file = st.file_uploader("Carica un file JSON con i risultati validi", type=["json"])

    if uploaded_file:
        df_json = pd.read_json(uploaded_file)
        st.dataframe(df_json)

        sender = EmailSender()

        all_emails = sender.extract_all_emails(df_json)
        if all_emails:
            example_site = df_json.iloc[0]["Sito Web"]
            with st.spinner("🧠 Generazione della mail..."):
                message = sender.generate_bulk_message(example_site)

            subject = "Proposta di Collaborazione"

            st.success("✅ Email generata. Verrà inviata a tutti i contatti elencati.")
            st.markdown("**Anteprima del messaggio:**")
            st.text_area("Messaggio", message, height=250)
            st.markdown(f"**Totale destinatari unici:** {len(all_emails)}")

            sender_email = st.text_input("Email mittente (es. Gmail)", value="", placeholder="nome@email.it")
            sender_password = st.text_input("Password applicazione (no password personale)", type="password")

            if st.button("📨 Invia Email a Tutti"):
                if not sender_email or not sender_password:
                    st.warning("Inserisci email e password.")
                else:
                    with st.spinner("📤 Invio email in corso..."):
                        results = []
                        for email in all_emails:
                            success, status = sender.send_email(
                                email, subject, message, sender_email, sender_password
                            )
                            results.append((email, status))
                    st.success("✅ Invio completato")
                    for email, status in results:
                        st.write(f"{email}: {status}")
        else:
            st.warning("Nessun indirizzo email trovato nel file caricato.")


if __name__ == "__main__":
    main()
