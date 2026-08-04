import re

with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# Replace missing[:50] with processing in chunks
new_fetch = """
def fetch_and_cache_missing_openalex_titles(w_ids: list, lookup: dict, output_dir: str):
    \"\"\"Automatically queries OpenAlex API in batch for missing cited W... IDs and caches results.\"\"\"
    missing = list(set([w.strip().lower() for w in w_ids if w.strip().lower() not in lookup and (w.startswith("W") or w.startswith("w"))]))
    if not missing:
        return

    import urllib.request
    new_entries = {}

    try:
        # Process in chunks of 50
        for i in range(0, len(missing), 50):
            chunk = [m.upper() for m in missing[i:i+50]]
            pipe_ids = "|".join(chunk)
            url = f"https://api.openalex.org/works?filter=openalex:{pipe_ids}&per_page=50"
            req = urllib.request.Request(url, headers={"User-Agent": "BibliometricPipeline/1.0"})

            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    # First create a map of original IDs to entries
                    returned_entries = {}
                    for item in data.get("results", []):
                        actual_wid = item.get("id", "").split("/")[-1].lower()
                        display_name = item.get("display_name", "")
                        yr = str(item.get("publication_year", ""))
                        authorships = item.get("authorships", [])
                        doi = item.get("doi", f"https://openalex.org/{actual_wid.upper()}")

                        display_name = display_name or "Unknown Title"
                        if authorships:
                            author_name = authorships[0].get("author", {}).get("display_name", "")
                            first_au = author_name.split()[-1] if author_name else "Unknown"
                            words = display_name.split()
                            short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                            title_str = f"{first_au} et al. ({yr}) {short_t}" if yr else f"{first_au} et al. {short_t}"
                        else:
                            words = display_name.split()
                            title_str = " ".join(words[:4]) + ("..." if len(words) > 4 else "")

                        entry = (title_str, doi if doi else f"https://openalex.org/{actual_wid.upper()}")
                        returned_entries[actual_wid] = entry

                        # Also check 'ids' field for merged/old IDs that we might have requested
                        openalex_id = item.get("ids", {}).get("openalex")
                        if isinstance(openalex_id, str):
                            old_id = openalex_id.split("/")[-1].lower()
                            returned_entries[old_id] = entry

                    # Now assign the found entries back to the original requested IDs
                    for req_id in missing[i:i+50]:
                        if req_id in returned_entries:
                            lookup[req_id] = returned_entries[req_id]
                            new_entries[req_id] = returned_entries[req_id]

                    # Fallback for IDs that still failed in the batch query
                    still_missing = [m for m in missing[i:i+50] if m not in new_entries]
                    for sm in still_missing:
                        try:
                            url_single = f"https://api.openalex.org/works/{sm.upper()}"
                            req_single = urllib.request.Request(url_single, headers={"User-Agent": "BibliometricPipeline/1.0"})
                            with urllib.request.urlopen(req_single, timeout=5) as resp_single:
                                item = json.loads(resp_single.read().decode('utf-8'))
                                actual_wid = item.get("id", "").split("/")[-1].lower()
                                display_name = item.get("display_name", "")
                                yr = str(item.get("publication_year", ""))
                                authorships = item.get("authorships", [])
                                doi = item.get("doi", f"https://openalex.org/{actual_wid.upper()}")

                                display_name = display_name or "Unknown Title"
                                if authorships:
                                    author_name = authorships[0].get("author", {}).get("display_name", "")
                                    first_au = author_name.split()[-1] if author_name else "Unknown"
                                    words = display_name.split()
                                    short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                                    title_str = f"{first_au} et al. ({yr}) {short_t}" if yr else f"{first_au} et al. {short_t}"
                                else:
                                    words = display_name.split()
                                    title_str = " ".join(words[:4]) + ("..." if len(words) > 4 else "")

                                entry = (title_str, doi if doi else f"https://openalex.org/{actual_wid.upper()}")
                                lookup[sm] = entry
                                new_entries[sm] = entry
                        except Exception as ex:
                            pass
            except Exception as e:
                logger.warning(f"Batch query failed for chunk: {e}")

        if new_entries:
            cache_path = os.path.join(output_dir, "data", "openalex_title_cache.json")
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            existing = {}
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    pass
            existing.update(new_entries)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not fetch missing cited titles from OpenAlex API: {e}")
"""

# replace the block using regex
pattern = re.compile(r'def fetch_and_cache_missing_openalex_titles.*?logger\.warning\(f"Could not fetch missing cited titles from OpenAlex API: \{e\}"\)', re.DOTALL)
content = pattern.sub(new_fetch.strip(), content)

with open("src/core/exporters/cocitation_exporter.py", "w") as f:
    f.write(content)
