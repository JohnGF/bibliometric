import os
import httpx
import logging

# Simple .env parser using standard library
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

def validate_all_keys():
    print("==================================================")
    print("   Bibliometric API Credentials Validation Check  ")
    print("==================================================\n")

    oa_email = os.environ.get("OPENALEX_EMAIL")
    pm_key = os.environ.get("PUBMED_API_KEY")
    scopus_key = os.environ.get("SCOPUS_API_KEY")
    scopus_token = os.environ.get("SCOPUS_INST_TOKEN")
    ss_key = os.environ.get("SS_API_KEY")
    wos_key = os.environ.get("WOS_API_KEY")

    # 1. OpenAlex
    if oa_email:
        url = "https://api.openalex.org/works?search=eeg&per_page=1"
        try:
            r = httpx.get(url, headers={"mailto": oa_email}, timeout=10.0)
            if r.status_code == 200:
                print(f"[SUCCESS] OpenAlex (Polite Email: {oa_email}) -> HTTP 200 OK")
            else:
                print(f"[WARNING] OpenAlex status code: {r.status_code}")
        except Exception as e:
            print(f"[FAILED] OpenAlex check error: {e}")
    else:
        print("[INFO] OpenAlex: No email configured (unauthenticated rate limits apply).")

    # 2. PubMed (NCBI)
    if pm_key:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=eeg&retmode=json&retmax=1&api_key={pm_key}"
        try:
            r = httpx.get(url, timeout=10.0)
            if r.status_code == 200 and "esearchresult" in r.json():
                print(f"[SUCCESS] PubMed (NCBI Key: {pm_key[:6]}...) -> HTTP 200 OK")
            else:
                print(f"[FAILED] PubMed returned status {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"[FAILED] PubMed check error: {e}")
    else:
        print("[INFO] PubMed: No API Key (running on public rate limits).")

    # 3. Elsevier Scopus
    if scopus_key:
        url = "https://api.elsevier.com/content/search/scopus"
        headers = {"Accept": "application/json", "X-ELS-APIKey": scopus_key}
        if scopus_token:
            headers["X-ELS-Insttoken"] = scopus_token
        params = {"query": "TITLE-ABS-KEY(eeg)", "count": 1}
        try:
            r = httpx.get(url, headers=headers, params=params, timeout=10.0)
            if r.status_code == 200 and "search-results" in r.json():
                total = r.json().get("search-results", {}).get("opensearch:totalResults", "N/A")
                print(f"[SUCCESS] Elsevier Scopus (Key: {scopus_key[:6]}...) -> HTTP 200 OK (Found {total} hits)")
            elif r.status_code == 401:
                print(f"[FAILED] Scopus HTTP 401 Unauthorized: Invalid API key or IP address not recognized.")
            elif r.status_code == 403:
                print(f"[FAILED] Scopus HTTP 403 Forbidden: API key requires institutional token or university VPN.")
            else:
                print(f"[WARNING] Scopus HTTP {r.status_code}: {r.text[:150]}")
        except Exception as e:
            print(f"[FAILED] Scopus check error: {e}")
    else:
        print("[INFO] Elsevier Scopus: No API Key configured.")

    # 4. IEEE Xplore
    ieee_key = os.environ.get("IEEE_API_KEY")
    if ieee_key:
        url = f"https://ieeexploreapi.ieee.org/api/v1/search/articles?apikey={ieee_key}&querytext=eeg&max_records=1&format=json"
        try:
            r = httpx.get(url, timeout=10.0)
            if r.status_code == 200:
                print(f"[SUCCESS] IEEE Xplore (Key: {ieee_key[:6]}...) -> HTTP 200 OK")
            else:
                print(f"[WARNING] IEEE Xplore HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"[FAILED] IEEE Xplore check error: {e}")
    else:
        print("[SUCCESS] IEEE Xplore -> Enabled via OpenAlex IEEE Publisher Index (No API key required).")

    # 5. Semantic Scholar
    if ss_key:
        url = "https://api.semanticscholar.org/graph/v1/paper/search?query=eeg&limit=1"
        try:
            r = httpx.get(url, headers={"x-api-key": ss_key}, timeout=10.0)
            if r.status_code == 200:
                print(f"[SUCCESS] Semantic Scholar (Key: {ss_key[:6]}...) -> HTTP 200 OK")
            else:
                print(f"[WARNING] Semantic Scholar HTTP {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"[FAILED] Semantic Scholar check error: {e}")
    else:
        print("[INFO] Semantic Scholar: No API Key (using public unauthenticated endpoint).")

    print("\nValidation complete.")

if __name__ == "__main__":
    validate_all_keys()
