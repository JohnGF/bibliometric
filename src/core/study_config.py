import os
import re

_QUERY_FILE = "query.txt"
_YEAR_RE = re.compile(r"^\s*(start-year|end-year)\s*[:=]\s*(\d{4})\s*$", re.IGNORECASE)


def find_query_file(start_dir: str = None) -> str:
    """Locate the query configuration file relative to cwd/repo root."""
    candidates = []
    if start_dir:
        candidates.append(os.path.join(start_dir, "data", _QUERY_FILE))
        candidates.append(os.path.join(start_dir, _QUERY_FILE))

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates.extend([
        os.path.join(os.getcwd(), "data", _QUERY_FILE),
        os.path.join(repo_root, "data", _QUERY_FILE),
        os.path.join(os.getcwd(), _QUERY_FILE),
        os.path.join(repo_root, _QUERY_FILE),
    ])

    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if os.path.exists(path):
            return path
    return None


def load_study_config(query_file: str = None) -> dict:
    """Parse the query file into {'query', 'start_year', 'end_year', 'source'}.

    Non-comment lines form the query string; `start-year:`/`end-year:` lines
    provide the study period used by analysis and LaTeX export scripts.
    """
    config = {"query": None, "start_year": None, "end_year": None, "source": None}

    path = query_file or find_query_file()
    if not path:
        return config

    config["source"] = path
    query_lines = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = _YEAR_RE.match(line)
            if m:
                key = "start_year" if m.group(1).lower() == "start-year" else "end_year"
                config[key] = int(m.group(2))
                continue
            query_lines.append(line)

    if query_lines:
        config["query"] = " ".join(query_lines)

    return config
