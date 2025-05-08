import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

st.set_page_config(page_title="Aziende Italiane per Fatturato", layout="wide")

BASE_URL = "https://www.fatturatoitalia.it"
HEADERS = {"User-Agent": "Mozilla/5.0"}

@st.cache_data(ttl=86400)
def fetch_company_list():
    url = f"{BASE_URL}"
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select(".company-listing a")
    return [(a.text.strip(), BASE_URL + a['href']) for a in links]

def extract_company_info(url):
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")
    data = {}
    for row in soup.select(".company-info tr"):
        cols = row.find_all("td")
        if len(cols) == 2:
            label = cols[0].text.strip().replace(":", "")
            value = cols[1].text.strip()
            data[label] = value
    return data

def filter_companies(companies, regione, fatturato_min):
    filtered = []
    for name, link in companies:
        info = extract_company_info(link)
        if regione and info.get("Regione") != regione:
            continue
        try:
            fatturato = info.get("Fatturato 2023", "0").replace("\u20ac", "").replace(".", "").replace(",", ".")
            fatturato_val = float(fatturato)
            if fatturato_val < fatturato_min:
                continue
        except:
            continue
        info["Nome Azienda"] = name
        filtered.append(info)
    return filtered

def main():
    st.title("🏢 Analisi Aziende Italiane da FatturatoItalia.it")
    st.markdown("Filtra le aziende italiane per **regione** e **fatturato minimo**.")

    regione = st.selectbox("Regione", ["", "Piemonte", "Lombardia", "Lazio", "Veneto", "Emilia-Romagna", "Toscana"])
    fatturato_min = st.number_input("Fatturato Minimo (€)", min_value=0, step=1000000, value=10000000)

    if st.button("🔍 Cerca Aziende"):
        st.info("Recupero lista aziende, attendi...")
        companies = fetch_company_list()
        results = filter_companies(companies, regione, fatturato_min)

        if results:
            df = pd.DataFrame(results)
            st.success(f"Trovate {len(df)} aziende che soddisfano i criteri.")
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Scarica in CSV", csv, "aziende_filtrate.csv", "text/csv")
        else:
            st.warning("Nessuna azienda trovata con i criteri selezionati.")

if __name__ == "__main__":
    main()
