import streamlit as st
import pandas as pd
import random
import time
from urllib.parse import urlparse
from duckduckgo_search import DDGS
import cloudscraper
from bs4 import BeautifulSoup
import re
from llama_cpp import Llama

# Impostazioni per Streamlit
st.set_page_config(page_title="Trova Clienti", layout="wide")

# Regex per estrarre le email
EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Crea il scraper per l'analisi dei siti
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False},
    disableCloudflareV1=True
)

# Inizializzazione del modello LLM locale (Mistral)
llm = Llama(model_path="models/mistral-7b-instruct-v0.1.Q4_K_M.gguf", n_ctx=2048)

# Funzione per generare la query avanzata usando LLM locale
def generate_advanced_query(settore, dimensione, regione):
    prompt = (
        f"Sei un esperto di marketing e lead generation. Genera una query di ricerca dettagliata e naturale "
        f"per trovare aziende italiane nel settore '{settore}', con dimensione '{dimensione}', situate in '{regione}'. "
        f"Fornisci una frase adatta per cercare su motori di ricerca come DuckDuckGo,"
        f"Ritorna solo ed esclusivamente la query senza punteggiatura cercando di essere più coinciso possibile ed ometti informazioni irrilevanti."
    )
    output = llm(prompt=f"[INST] {prompt} [/INST]", max_tokens=100, temperature=0.7, stop=["</s>"])
    return output["choices"][0]["text"].strip()

# Funzione per cercare su DuckDuckGo
def duckduckgo_search_sites(query, max_results=10):
    results = set()
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results * 5):
            url = r.get("url") or r.get("href")
            if url and url.startswith("http"):
                results.add(urlparse(url).scheme + "://" + urlparse(url).netloc)
    return list(results)

# Funzione per estrarre le email da una pagina HTML
def extract_emails_from_url(url):
    try:
        response = scraper.get(url, timeout=10)
        if response.status_code != 200:
            return [], f"Errore HTTP {response.status_code} - {response.reason} ({url})"

        base_emails = extract_clean_emails(response.text)
        contact_emails, contact_statuses = try_common_contact_pages(url)
        all_emails = list(set(base_emails + contact_emails))

        if all_emails:
            return all_emails, "Email trovate con successo"
        else:
            return [], f"Nessuna email valida trovata (pagina principale + {', '.join(contact_statuses)})"

    except Exception as e:
        if "certificate verify failed" in str(e):
            return [], f"Sito con SSL non valido ({url})"
        elif "bad character range" in str(e):
            return [], f"Regex malformato: controlla la definizione di EMAIL_REGEX"
        return [], f"Errore di richiesta: {str(e)} ({url})"

# Funzione per estrarre le email dal testo della pagina HTML
def extract_clean_emails(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    mailtos = [a.get("href")[7:] for a in soup.find_all("a", href=True) if a.get("href", "").startswith("mailto:")]
    text_emails = re.findall(EMAIL_REGEX, soup.get_text().lower())
    header = soup.find("header")
    footer = soup.find("footer")
    header_emails = re.findall(EMAIL_REGEX, header.get_text().lower()) if header else []
    footer_emails = re.findall(EMAIL_REGEX, footer.get_text().lower()) if footer else []
    all_emails = list(set(mailtos + text_emails + header_emails + footer_emails))
    clean_emails = [
        e for e in all_emails
        if not any(bad in e.lower() for bad in ["pec", "linkedin", "telefono", "fax"])
           and "@" in e and "." in e.split("@")[1]
           and len(e.split("@")[0]) > 2
    ]
    return clean_emails

# Funzione per controllare le pagine di contatto comuni
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

# Funzione principale di Streamlit
def main():
    st.title("🔍 Ricerca Clienti Aziendali + Email")
    st.markdown("Seleziona i filtri per migliorare la qualità dei risultati di ricerca.")

    col1, col2, col3 = st.columns(3)

    with col1:
        settore = st.selectbox("Settore", ["", "Risorse Umane", "Informatica", "Marketing", "Finanza"])

    with col2:
        regioni_italiane = [
            "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia-Romagna", "Friuli Venezia Giulia",
            "Lazio", "Liguria", "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna", "Sicilia",
            "Toscana", "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto"
        ]
        regione = st.selectbox("Seleziona una Regione", regioni_italiane)

    with col3:
        dimensione = st.selectbox("Dimensione Aziendale", ["", "Piccola", "Media", "Grande"])

    max_results = st.slider("Numero massimo di siti da analizzare", 5, 50, 10)

    if st.button("Cerca Clienti"):
        query = generate_advanced_query(settore, dimensione, regione)

        st.info(f"Inizio ricerca per: '{query}'...")
        all_urls = duckduckgo_search_sites(query, max_results=max_results * 3)

        visited_domains = set()
        data_utili = []
        data_scartati = []
        progress = st.progress(0)
        valid_count = 0
        i = 0

        while valid_count < max_results and i < len(all_urls):
            url = all_urls[i]
            domain = urlparse(url).netloc
            if domain in visited_domains:
                i += 1
                continue

            visited_domains.add(domain)
            emails, status = extract_emails_from_url(url)

            result = {
                "Sito Web": domain,
                "Email trovate": ", ".join(emails) if emails else "Nessuna",
                "Stato": status
            }

            if emails:
                data_utili.append(result)
                valid_count += 1
            else:
                data_scartati.append(result)

            i += 1
            progress.progress(min(i / max_results, 1.0))
            time.sleep(random.uniform(1.5, 3.5))

        if data_utili:
            st.success("✅ Risultati Utilizzabili")
            df_validi = pd.DataFrame(data_utili)
            st.dataframe(df_validi, use_container_width=True)
            json_results = df_validi.to_json(orient="records", lines=True)
            st.download_button("📥 Scarica risultati in JSON", json_results, "risultati.json", "application/json")
        else:
            st.warning("❗ Nessun risultato utilizzabile trovato.")

        if data_scartati:
            st.markdown("---")
            st.error("⚠️ Risultati Scartati")
            df_scartati = pd.DataFrame(data_scartati)
            st.dataframe(df_scartati, use_container_width=True)

if __name__ == "__main__":
    main()